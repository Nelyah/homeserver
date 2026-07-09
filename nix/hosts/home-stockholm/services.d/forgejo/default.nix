{...}: {
  name = "forgejo";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "forgejo";
      deployments = ["forgejo-runner" "forgejo" "forgejo-db"];
      pvcs = ["forgejo-data" "forgejo-db"];
    };
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
