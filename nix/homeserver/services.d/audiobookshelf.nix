{ config, ... }:
{
  name = "audiobookshelf";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/audiobookshelf/docker-compose.yml";
    networks = [ "audiobookshelf" ];
    volumes = [
      "audiobookshelf_db"
      "audiobookshelf_metadata"
    ];
  };
  backup = {
    enable = true;
    volumes = [
      "audiobookshelf_db"
      "audiobookshelf_metadata"
    ];
  };
}
