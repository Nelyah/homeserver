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
  # Returns: bash script fragment
  mkCopyScript = { rsyncBin, serviceName, packagePath, deployRoot }: ''
    echo "Deploying ${serviceName}..."
    mkdir -p "${deployRoot}/${serviceName}"
    ${lib.optionalString (packagePath != null) ''
      if [ -z "${packagePath}" ]; then
        echo "Package path for ${serviceName} is empty; aborting"
        exit 1
      fi
      # Copy files from nix store (preserve symlinks in target)
      ${rsyncBin} -a --delete --exclude='.env' "${packagePath}/" "${deployRoot}/${serviceName}/"

      # Set permissions: files read-only, directories executable
      find "${deployRoot}/${serviceName}" -type f ! -name '.env' -exec chmod 0444 {} \; 2>/dev/null || true
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
      if [ -f "${secretsRoot}/docker-services/${serviceName}/${spec.destination}" ]; then
        ln -sf "${secretsRoot}/docker-services/${serviceName}/${spec.destination}" \
               "${deployRoot}/${serviceName}/${spec.destination}" 2>/dev/null || true
      fi
    '') (lib.attrValues secretFiles);
}
