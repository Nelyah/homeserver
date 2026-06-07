{...}: {
  name = "caddy";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "caddy";
      deployments = ["caddy"];
      pvcs = ["caddy-data"];
    };
  };
}
