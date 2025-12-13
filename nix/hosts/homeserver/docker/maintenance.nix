# Docker maintenance tasks: log cleanup and image pruning
{pkgs, ...}: {
  environment.systemPackages = [
    (pkgs.writeShellScriptBin "docker-fix-logs" ''
      #!${pkgs.bash}/bin/bash
      set -euo pipefail
      for container_id in $(journalctl --since '1 hour ago' -u docker | \
                              grep "Error streaming logs.*invalid character" | \
                              sed -r 's/^.*container=([^ ]+) .*/\1/' | \
                              sort -u); do
          echo >&2 "Truncating corrupted logs for container $container_id"
          truncate -s0 "$(${pkgs.docker}/bin/docker container inspect --format='{{.LogPath}}' "$container_id")"
      done
    '')
  ];

  systemd.services.docker-fix-logs = {
    description = "Truncate corrupted docker logs";
    script = "${pkgs.bash}/bin/bash /run/current-system/sw/bin/docker-fix-logs";
    serviceConfig.Type = "oneshot";
  };

  systemd.timers.docker-fix-logs = {
    wantedBy = ["timers.target"];
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
      ExecStart = "/run/current-system/sw/bin/svc docker prune-images";
    };
  };

  systemd.timers.docker-images-cleanup = {
    wantedBy = ["timers.target"];
    timerConfig.OnCalendar = "03:00";
  };
}
