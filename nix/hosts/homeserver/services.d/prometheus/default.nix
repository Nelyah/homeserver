{config, pkgs, lib, ...}: {
  name = "prometheus";
  compose = {
    enable = true;
    networks = ["grafana"];
    volumes = [
      "prometheus_data"
      "prometheus_config"
    ];
  };
  files = {
    "prometheus_config.yml".source = ./prometheus_config.yml;
    "exporters" = {
      source = ./exporters;
      destination = "exporters";
      executable = false;
    };
  };
  backup = {
    enable = true;
    volumes = ["prometheus_data"];
  };
}
