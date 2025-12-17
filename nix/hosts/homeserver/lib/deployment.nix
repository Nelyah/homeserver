# Pure helper functions for service deployment
# These functions take data and return script strings
{ lib }:

{
  # Generate script fragment to remove stale service directories
  # enabledServiceNames: ["prometheus" "grafana"]
  # Returns: bash script fragment
  mkCleanupScript = { deployRoot, enabledServiceNames }: ''
    # Remove stale service directories (services no longer enabled)
    if [ -d "${deployRoot}" ]; then
      for dir in "${deployRoot}"/*/; do
        [ -d "$dir" ] || continue
        svc_name=$(basename "$dir")
        found=0
        for enabled in ${lib.concatMapStringsSep " " (n: ''"${n}"'') enabledServiceNames}; do
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
  '';

  # Generate script fragment to copy files for a service
  # rsyncBin: "${pkgs.rsync}/bin/rsync"
  # serviceName: "prometheus"
  # packagePath: "/nix/store/xxx-docker-service-prometheus" or null
  # exclude: list of patterns to exclude from rsync (e.g. [".env"])
  # Returns: bash script fragment
  mkCopyScript = {
    rsyncBin,
    serviceName,
    packagePath,
    deployRoot,
    exclude ? [],
  }: let
    rsyncExcludeArgs =
      lib.concatMapStringsSep " " (d: "--exclude='${d}'") exclude;
  in ''
    echo "Deploying ${serviceName}..."
    mkdir -p "${deployRoot}/${serviceName}"
    ${lib.optionalString (packagePath != null) ''
      if [ -z "${packagePath}" ]; then
        echo "Package path for ${serviceName} is empty; aborting"
        exit 1
      fi
      # Copy files from nix store (preserve symlinks in target)
      ${rsyncBin} -a --delete ${rsyncExcludeArgs} "${packagePath}/" "${deployRoot}/${serviceName}/"

      # Set permissions: keep exec bits but strip write permissions.
      find "${deployRoot}/${serviceName}" -type f -exec chmod a-w {} \; 2>/dev/null || true
      find "${deployRoot}/${serviceName}" -type d -exec chmod 0755 {} \; 2>/dev/null || true
    ''}
  '';

  # Generate script fragment to create symlinks for secret files
  # secretsRoot: config.homeserver.paths.secretsRoot
  # deployRoot: "/var/lib/docker-services"
  # serviceName: "prometheus"
  # secretFiles: attrset of { destination = "..."; ... }
  # Returns: bash script fragment
  mkSymlinkScript = { secretsRoot, deployRoot, serviceName, secretFiles }:
    lib.concatMapStringsSep "\n" (spec: ''
      secret_src="${secretsRoot}/docker-services/${serviceName}/${spec.destination}"
      secret_dst="${deployRoot}/${serviceName}/${spec.destination}"

      if [ ! -f "$secret_src" ]; then
        echo -e "\033[33mWARNING: Secret file not rendered. Re-run vault-agent: $secret_src\033[0m" >&2
        echo -e "\033[33mCheck vault-agent logs: journalctl -u vault-agent\033[0m" >&2
      else
        if ! ln -sf "$secret_src" "$secret_dst"; then
          echo "Failed to create symlink for ${serviceName}/${spec.destination}" >&2
          exit 1
        fi
      fi
    '') (lib.attrValues secretFiles);
}
