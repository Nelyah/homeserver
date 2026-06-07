{...}: {
  name = "atuin";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "atuin";
      deployments = ["atuin" "atuin-db"];
      pvcs = ["atuin-config" "atuin-db"];
    };
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
