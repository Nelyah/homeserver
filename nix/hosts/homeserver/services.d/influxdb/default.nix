{config, pkgs, lib, ...}: {
  name = "influxdb";
  compose = {
    enable = true;
    networks = ["grafana"];
    volumes = ["influxdb_data"];
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/influxdb" -}}
        DOCKER_INFLUXDB_INIT_MODE=setup
        DOCKER_INFLUXDB_INIT_USERNAME={{ .Data.data.DOCKER_INFLUXDB_INIT_USERNAME }}
        DOCKER_INFLUXDB_INIT_PASSWORD={{ .Data.data.DOCKER_INFLUXDB_INIT_PASSWORD }}
        DOCKER_INFLUXDB_INIT_ORG={{ .Data.data.DOCKER_INFLUXDB_INIT_ORG }}
        DOCKER_INFLUXDB_INIT_BUCKET=Measurements
        DOCKER_INFLUXDB_INIT_CLI_CONFIG_NAME=homeserver
        {{ end -}}
      '';
    };
  };
  backup = {
    enable = true;
    volumes = ["influxdb_data"];
  };
}
