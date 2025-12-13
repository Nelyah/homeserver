# Deployment module for docker service files
# Handles copying files from Nix store to /var/lib/docker-services/
# and creating symlinks for vault-rendered secret files
{
  lib,
  pkgs,
  config,
  ...
}: let
  homeserverLib = import ../lib { inherit lib; };

  # Use centralized paths from options
  deployRoot = config.homeserver.paths.deployRoot;
  secretsRoot = config.homeserver.paths.secretsRoot;

  # Read services from config (populated by services.nix module)
  services = config.homeserver.services;

  # Filter services with compose enabled
  enabledServices = homeserverLib.docker.filterEnabledCompose services;

  # Filter services with secret files defined
  servicesWithSecretFiles = homeserverLib.docker.filterWithSecretFiles services;

  # Build a derivation containing all files for a service
  mkServicePackage = name: svc: let
    files = svc.files or {};
    hasFiles = files != {};
  in
    if hasFiles
    then
      pkgs.runCommand "docker-service-${name}" {} ''
        mkdir -p $out
        ${lib.concatStringsSep "\n" (lib.mapAttrsToList (fname: spec: let
          dest = if spec.destination != null then spec.destination else fname;
        in ''
          mkdir -p "$out/$(dirname "${dest}")"
          cp -r "${spec.source}" "$out/${dest}"
          ${lib.optionalString spec.executable ''chmod +x "$out/${dest}"''}
        '') files)}
      ''
    else null;

  servicePackages = lib.mapAttrs mkServicePackage enabledServices;

  # List of enabled service names for the deployment script
  enabledServiceNames = lib.attrNames enabledServices;
  servicesWithSecretFilesNames = lib.attrNames servicesWithSecretFiles;

  # Deployment script
  deployScript = pkgs.writeShellScript "deploy-docker-services" ''
    set -euo pipefail

    DEPLOY_ROOT="${deployRoot}"
    SECRETS_ROOT="${secretsRoot}"
    ENABLED_SERVICES=(${lib.concatStringsSep " " (map (n: ''"${n}"'') enabledServiceNames)})
    SYSTEMCTL="${pkgs.systemd}/bin/systemctl"

    if [ -z "$DEPLOY_ROOT" ]; then
      echo "DEPLOY_ROOT is empty; aborting"
      exit 1
    fi

    echo "Deploying docker services to $DEPLOY_ROOT..."

    # Remove stale service directories (services no longer enabled)
    ${homeserverLib.deployment.mkCleanupScript {
      deployRoot = "$DEPLOY_ROOT";
      inherit enabledServiceNames;
    }}

    # Deploy each service
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: svc: let
      pkg = servicePackages.${name};
      secretDests = lib.mapAttrsToList (_: spec: spec.destination) (svc.secretFiles or {});
    in
      homeserverLib.deployment.mkCopyScript {
        rsyncBin = "${pkgs.rsync}/bin/rsync";
        serviceName = name;
        packagePath = pkg;
        deployRoot = "$DEPLOY_ROOT";
        exclude = secretDests;
      }
    ) enabledServices)}

    # Create symlinks for secret files (including .env)
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: svc:
      homeserverLib.deployment.mkSymlinkScript {
        secretsRoot = "$SECRETS_ROOT";
        deployRoot = "$DEPLOY_ROOT";
        serviceName = name;
        secretFiles = svc.secretFiles or {};
      }
    ) servicesWithSecretFiles)}

    # Recover failed compose units without restarting healthy/running stacks.
    # This avoids a redeploy causing a restart of every service.
    for svc in "''${ENABLED_SERVICES[@]}"; do
      unit="docker-compose-''${svc}.service"
      load_state="$("$SYSTEMCTL" show -p LoadState --value "$unit" 2>/dev/null || true)"
      if [ -z "$load_state" ] || [ "$load_state" = "not-found" ]; then
        continue
      fi

      if "$SYSTEMCTL" --quiet is-failed "$unit"; then
        echo "Unit $unit is failed; resetting and restarting"
        "$SYSTEMCTL" reset-failed "$unit" || true
        "$SYSTEMCTL" restart "$unit" || true
      fi
    done

    echo "Docker services deployed successfully"
  '';

in lib.mkIf (enabledServices != {}) {
  # Create base directories
  systemd.tmpfiles.rules = [
    "d ${deployRoot} 0755 root root -"
  ] ++ map (name: "d ${deployRoot}/${name} 0755 root root -") enabledServiceNames
    ++ map (name: "d ${secretsRoot}/docker-services/${name} 0700 root root -") servicesWithSecretFilesNames;

  # Run deployment as activation script
  system.activationScripts.deployDockerServices = {
    text = "${deployScript}";
    deps = ["specialfs" "users" "groups"];
  };
}
