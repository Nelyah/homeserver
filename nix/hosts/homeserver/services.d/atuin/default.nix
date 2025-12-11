{config, pkgs, lib, ...}: {
  name = "atuin";
  compose = {
    enable = true;
    networks = [];
    volumes = [
      "atuin_db"
      "atuin_redis"
      "atuin_config"
    ];
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/atuin" -}}
        ATUIN_DB_NAME=atuin
        ATUIN_DB_USERNAME=atuin
        ATUIN_DB_PASSWORD={{ .Data.data.DB_PASSWORD }}
        {{ end -}}
      '';
    };
  };
  backup = {
    enable = true;
    pre = ''
      dump="/tmp/atuin_db.sql"
      ${pkgs.docker}/bin/docker exec atuin_db sh -c "pg_dump -U atuin" > "$dump"
    '';
    post = ''rm -f "$dump"'';
    paths = ["/tmp/atuin_db.sql"];
    volumes = [
      "atuin_db"
      "atuin_redis"
    ];
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
