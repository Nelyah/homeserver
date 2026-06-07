{...}: {
  name = "navidrome";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "navidrome";
      deployments = ["navidrome"];
      pvcs = ["navidrome-data"];
    };
  };
}
