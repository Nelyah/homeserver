{config, lib, ...}: {
  name = "grafana";
  compose = {
    enable = true;
    networks = ["grafana"];
    volumes = ["grafana_data"];
  };
  files = {
    "loki_config.yml".source = ./loki_config.yml;
    "promtail_config.yml".source = ./promtail_config.yml;
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = ["grafana_data"];
  };
}
