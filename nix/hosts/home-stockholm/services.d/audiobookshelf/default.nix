{...}: {
  name = "audiobookshelf";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "audiobookshelf";
      deployments = ["audiobookshelf"];
      pvcs = ["audiobookshelf-db" "audiobookshelf-metadata"];
    };
  };
}
