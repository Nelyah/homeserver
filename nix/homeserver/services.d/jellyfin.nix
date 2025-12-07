{ config, ... }:
{
  name = "jellyfin";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/jellyfin/docker-compose.yml";
    networks = [ "frontend" ];
    volumes = [
      "jellyfin_config"
      "jellyfin_cache"
    ];
  };
  backup = {
    enable = true;
    volumes = [
      "jellyfin_config"
      "jellyfin_cache"
    ];
  };
}
