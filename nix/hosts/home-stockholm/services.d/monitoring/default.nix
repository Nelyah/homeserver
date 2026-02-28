{...}: {
  name = "monitoring";
  compose = {
    enable = true;
    networks = ["monitoring"];
    volumes = [
      "grafana_data"
      "influxdb_data"
      "prometheus_data"
    ];
  };
  files = {
    "loki_config.yml".source = ./loki_config.yml;
    "prometheus_config.yml".source = ./prometheus_config.yml;
    "promtail_config.yml".source = ./promtail_config.yml;
    "grafana.ini".source = ./grafana.ini;
  };
  secretFiles = {
    "influxdb.env" = {
      destination = "influxdb.env";
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
    needsServiceStopped = true;
    volumes = ["grafana_data" "influxdb_data" "prometheus_data"];
  };
}
