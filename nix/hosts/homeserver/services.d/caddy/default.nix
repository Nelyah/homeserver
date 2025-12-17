{config, pkgs, lib, ...}: {
  name = "caddy";
  compose = {
    enable = true;
    networks = [
      "audiobookshelf"
      "frontend"
      "emby"
      "monitoring"
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
  files = {
    "Caddyfile".source = ./Caddyfile;
  };
  backup = {
    enable = true;
    volumes = ["caddy_data"];
  };
}
