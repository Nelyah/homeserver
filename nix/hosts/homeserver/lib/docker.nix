# Pure helper functions for Docker infrastructure
# These functions take service data and return derived values
{ lib }:

{
  # Collect unique network names from enabled compose services
  # services: attrset of services with compose.networks
  # Returns: ["backend" "frontend" "grafana"]
  collectNetworks = services:
    lib.unique (
      lib.flatten (
        lib.mapAttrsToList (_: svc: svc.compose.networks or []) services
      )
    );

  # Collect unique volume names from enabled compose services
  # services: attrset of services with compose.volumes
  # Returns: ["prometheus_data" "grafana_data"]
  collectVolumes = services:
    lib.unique (
      lib.flatten (
        lib.mapAttrsToList (_: svc: svc.compose.volumes or []) services
      )
    );

  # Generate script to create docker networks and volumes
  # dockerBin: "${pkgs.docker}/bin/docker"
  # networks: ["backend" "frontend"]
  # volumes: ["prometheus_data"]
  # Returns: bash script fragment
  mkPrereqScript = { dockerBin, networks, volumes }: ''
    set -e
    for n in ${lib.concatStringsSep " " networks}; do
      ${dockerBin} network create "$n" >/dev/null 2>&1 || true
    done
    for v in ${lib.concatStringsSep " " volumes}; do
      ${dockerBin} volume create "$v" >/dev/null 2>&1 || true
    done
  '';

  # Filter services with compose enabled
  # services: attrset of all services
  # Returns: attrset of services where compose.enable = true
  filterEnabledCompose = services:
    lib.filterAttrs (
      _: svc: (svc.compose or null) != null && (svc.compose.enable or false)
    ) services;

  # Filter services with backup enabled
  # services: attrset of all services
  # Returns: attrset of services where backup.enable = true
  filterEnabledBackup = services:
    lib.filterAttrs (
      _: svc: (svc.backup or null) != null && (svc.backup.enable or false)
    ) services;

  # Filter services with secret files defined
  # services: attrset of all services
  # Returns: attrset of services with non-empty secretFiles
  filterWithSecretFiles = services:
    lib.filterAttrs (
      _: svc: (svc.compose.enable or false) && (svc.secretFiles or {}) != {}
    ) services;
}
