{config, ...}: {
  name = "music";
  backup = {
    enable = true;
    paths = [
      "${config.homeserver.mainDrive}/music/library"
      "${config.homeserver.mainDrive}/music/beets-library.db"
      "${config.homeserver.mainDrive}/music/library_mum"
    ];
  };
}
