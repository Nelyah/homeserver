{...}: {
  name = "vault";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "vault";
      deployments = ["vault"];
      pvcs = ["vault-data"];
    };
  };
}
