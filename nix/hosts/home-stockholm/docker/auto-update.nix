# Automatic Docker container image updates
# Daily timer that pulls latest images and recreates containers if changed
{
  pkgs,
  config,
  ...
}: let
  docker = "${pkgs.docker}/bin/docker";
  compose = "${pkgs.docker-compose}/bin/docker-compose";
  deployRoot = config.homeserver.paths.deployRoot;

  updateScript = pkgs.writeShellScript "docker-auto-update" ''
    set -euo pipefail

    for service_dir in "${deployRoot}"/*/; do
      [ -d "$service_dir" ] || continue
      service_name=$(basename "$service_dir")
      compose_file="$service_dir/docker-compose.yml"
      [ -f "$compose_file" ] || continue

      echo "Updating $service_name..."
      cd "$service_dir"

      # Pull latest images and recreate containers if image changed
      ${compose} up -d --pull always --quiet-pull --remove-orphans 2>/dev/null || true
    done

    # Cleanup old images (older than 24h, not in use)
    ${docker} image prune -f --filter "until=24h" >/dev/null
  '';
in {
  systemd.services.docker-auto-update = {
    description = "Pull and update Docker containers";
    after = ["docker.service"];
    wants = ["docker.service"];
    serviceConfig = {
      Type = "oneshot";
      ExecStart = updateScript;
    };
  };

  systemd.timers.docker-auto-update = {
    wantedBy = ["timers.target"];
    timerConfig = {
      OnCalendar = "04:00";
      Persistent = true;
    };
  };
}
