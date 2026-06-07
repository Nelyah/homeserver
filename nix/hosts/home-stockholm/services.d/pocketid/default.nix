{...}: {
  name = "pocketid";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "pocketid";
      deployments = ["tinyauth" "pocketid"];
      pvcs = ["pocketid-data" "tinyauth-data"];
    };
    tags = ["pocketid" "tinyauth"];
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
