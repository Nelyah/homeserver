{...}: {
  name = "uptime_kuma";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "uptime-kuma";
      deployments = ["uptime-kuma"];
      pvcs = ["uptime-kuma-data"];
    };
    policy = {
      daily = 10;
      weekly = 25;
      monthly = 12;
    };
  };
}
