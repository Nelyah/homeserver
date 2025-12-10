{config, pkgs, ...}: {
  name = "atuin";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/atuin/docker-compose.yml";
    networks = [];
    volumes = [
      "atuin_db"
      "atuin_redis"
      "atuin_config"
    ];
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
