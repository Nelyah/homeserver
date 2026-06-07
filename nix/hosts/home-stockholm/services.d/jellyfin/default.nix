{...}: {
  name = "jellyfin";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "jellyfin";
      deployments = ["jellyfin"];
      pvcs = ["jellyfin-config" "jellyfin-cache"];
    };
  };
}
