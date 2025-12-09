{config, ...}: {
  name = "influxdb";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/influxdb/docker-compose.yml";
    networks = ["grafana"];
    volumes = ["influxdb_data"];
  };
  backup = {
    enable = true;
    volumes = ["influxdb_data"];
  };
}
