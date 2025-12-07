{ config, ... }:
{
  name = "prometheus";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/prometheus/docker-compose.yml";
    networks = [ "grafana" ];
    volumes = [
      "prometheus_data"
      "prometheus_config"
    ];
  };
  backup = {
    enable = true;
    volumes = [ "prometheus_data" ];
  };
}
