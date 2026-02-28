{config, pkgs, lib, ...}: {
  name = "caddy";
  compose = {
    build = true;
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
      "pocketid"
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
    "Dockerfile".source = ./Dockerfile;
  };
  backup = {
    enable = true;
    volumes = ["caddy_data"];
  };
}
