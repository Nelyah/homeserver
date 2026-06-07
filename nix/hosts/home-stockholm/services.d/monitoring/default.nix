{...}: {
  name = "monitoring";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "monitoring";
      deployments = ["grafana" "prometheus" "influxdb"];
      pvcs = ["grafana-data" "influxdb-data" "prometheus-data"];
    };
  };
}
