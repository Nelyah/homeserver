{config, pkgs, lib, ...}: {
  name = "immich";
  compose = {
    enable = false;
    networks = [
      "frontend"
      "backend"
    ];
    volumes = [
      "immich_model_cache"
      "immich_db"
    ];
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      perms = "0400";
      template = ''
        {{ with secret "homeserver_secrets/data/immich" -}}
        DB_PASSWORD={{ .Data.data.DB_PASSWORD }}
        DB_USERNAME={{ .Data.data.DB_USERNAME }}
        DB_DATABASE_NAME={{ .Data.data.DB_DATABASE_NAME }}
        {{ end -}}
      '';
    };
  };
}
