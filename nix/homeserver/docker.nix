{
  pkgs,
  lib,
  config,
  ...
}:
let
  servicesDef = (import ./services.nix { inherit lib config; }).attrset;
  enabledCompose = lib.filterAttrs (
    _: service: (service.compose or null) != null && (service.compose.enabled or false)
  ) servicesDef;

  networks = lib.unique (
    lib.flatten (lib.mapAttrsToList (_: svc: svc.compose.networks or [ ]) enabledCompose)
  );
  volumes = lib.unique (
    lib.flatten (lib.mapAttrsToList (_: svc: svc.compose.volumes or [ ]) enabledCompose)
  );
in
{
  virtualisation.docker = {
    enable = true;
    enableOnBoot = true;
    daemon.settings."data-root" = "${config.homeserver.mainDrive}/docker-data";
  };

  environment.systemPackages = [
    pkgs.docker-compose
    (pkgs.writeShellScriptBin "docker-fix-logs" ''
      #!${pkgs.bash}/bin/bash
      set -euo pipefail
      for container_id in $(journalctl --since '1 hour ago' -u docker | \
                              grep "Error streaming logs.*invalid character" | \
                              sed -r 's/^.*container=([^ ]+) .*/\1/' | \
                              sort -u); do
          echo >&2 "Truncating corrupted logs for container $container_id"
          truncate -s0 "$(docker container inspect --format='{{.LogPath}}' "$container_id")"
      done
    '')
  ];

  # Create external networks/volumes referenced by compose stacks
  system.activationScripts.dockerPrereqs.text = ''
    set -e
    for n in ${lib.concatStringsSep " " networks}; do
      docker network create "$n" >/dev/null 2>&1 || true
    done
    for v in ${lib.concatStringsSep " " volumes}; do
      docker volume create "$v" >/dev/null 2>&1 || true
    done
  '';

  systemd.services.docker-fix-logs = {
    description = "Truncate corrupted docker logs";
    script = "${pkgs.bash}/bin/bash /run/current-system/sw/bin/docker-fix-logs";
    serviceConfig.Type = "oneshot";
  };

  systemd.timers.docker-fix-logs = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnBootSec = "10min";
      OnUnitActiveSec = "10min";
    };
  };

  # docker-images-cleanup timer/service
  systemd.services.docker-images-cleanup = {
    description = "Cleanup dangling docker images";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = "${config.homeserver.homeserverRoot}/bin/docker-images-cleanup";
    };
  };

  systemd.timers.docker-images-cleanup = {
    wantedBy = [ "timers.target" ];
    timerConfig.OnCalendar = "03:00";
  };
}
