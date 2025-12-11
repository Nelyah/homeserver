{config, pkgs, lib, ...}: {
  name = "audiobookshelf";
  compose = {
    enable = true;
    networks = ["audiobookshelf"];
    volumes = [
      "audiobookshelf_db"
      "audiobookshelf_metadata"
    ];
  };

  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        AUDIOBOOK_LIBRARY=${config.homeserver.mainDrive}/audiobooks
      '';
    };
  };

  backup = {
    enable = true;
    volumes = [
      "audiobookshelf_db"
      "audiobookshelf_metadata"
    ];
  };
}
