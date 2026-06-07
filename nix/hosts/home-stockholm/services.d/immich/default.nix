{...}: {
  name = "immich";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "immich";
      deployments = ["immich-server" "immich-machine-learning" "redis" "database"];
      pvcs = ["immich-db" "immich-model-cache"];
    };
  };
}
