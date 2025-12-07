{ config, ... }:
{
  name = "grafana";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/grafana/docker-compose.yml";
    networks = [ "grafana" ];
    volumes = [ "grafana_data" ];
  };
  backup = {
    enable = true;
    volumes = [ "grafana_data" ];
  };
}
