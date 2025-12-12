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

    if [ -z "$DEPLOY_ROOT" ]; then
      echo "DEPLOY_ROOT is empty; aborting"
      exit 1
    fi

    echo "Deploying docker services to $DEPLOY_ROOT..."

    # Remove stale service directories (services no longer enabled)
    if [ -d "$DEPLOY_ROOT" ]; then
      for dir in "$DEPLOY_ROOT"/*/; do
        [ -d "$dir" ] || continue
        svc_name=$(basename "$dir")
        found=0
        for enabled in "''${ENABLED_SERVICES[@]}"; do
          if [ "$svc_name" = "$enabled" ]; then
            found=1
            break
          fi
        done
        if [ $found -eq 0 ]; then
          echo "Removing stale service directory: $dir"
          rm -rf "$dir"
        fi
      done
    fi

    # Deploy each service
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: svc: let
      pkg = servicePackages.${name};
      hasPackage = pkg != null;
    in ''
      echo "Deploying ${name}..."
      mkdir -p "$DEPLOY_ROOT/${name}"

      ${lib.optionalString hasPackage ''
        if [ -z "${pkg}" ]; then
          echo "Package path for ${name} is empty; aborting"
          exit 1
        fi
        # Copy files from nix store (preserve symlinks in target)
        ${pkgs.rsync}/bin/rsync -a --delete --exclude='.env' "${pkg}/" "$DEPLOY_ROOT/${name}/"

        # Set permissions: files read-only, directories executable
        find "$DEPLOY_ROOT/${name}" -type f ! -name '.env' -exec chmod 0444 {} \; 2>/dev/null || true
        find "$DEPLOY_ROOT/${name}" -type d -exec chmod 0755 {} \; 2>/dev/null || true
      ''}
    '') enabledServices)}

    # Create symlinks for secret files (including .env)
    ${lib.concatStringsSep "\n" (lib.mapAttrsToList (name: svc: let
      secretFiles = svc.secretFiles or {};
    in lib.concatStringsSep "\n" (lib.mapAttrsToList (_fname: spec: ''
      if [ -f "$SECRETS_ROOT/docker-services/${name}/${spec.destination}" ]; then
        ln -sf "$SECRETS_ROOT/docker-services/${name}/${spec.destination}" "$DEPLOY_ROOT/${name}/${spec.destination}" 2>/dev/null || true
      fi
    '') secretFiles)) servicesWithSecretFiles)}

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
