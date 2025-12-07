{ config, ... }:
{
  name = "caddy";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/caddy/docker-compose.yml";
    networks = [
      "audiobookshelf"
      "frontend"
      "emby"
      "grafana"
      "ghost"
      "immich"
      "internal"
      "nextcloud"
      "navidrome"
      "pihole"
      "bookstack"
      "watchtower"
      "wordpress"
    ];
    volumes = [
      "caddy_data"
      "nextcloud_site"
    ];
  };
  backup = {
    enable = true;
    volumes = [ "caddy_data" ];
  };
}
