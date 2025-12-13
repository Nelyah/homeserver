{config, pkgs, lib, ...}: {
  name = "atuin";
  compose = {
    enable = true;
    networks = ["frontend" "backend"];
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
    needsServiceStopped = true;
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
