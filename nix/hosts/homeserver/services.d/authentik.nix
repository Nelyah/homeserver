{config, pkgs, ...}: {
  name = "authentik";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/authentik/docker-compose.yml";
    networks = [
      "backend"
      "frontend"
    ];
    volumes = [
      "authentik_db"
      "authentik_redis"
      "authentik_templates"
      "authentik_certs"
      "authentik_media"
    ];
  };
  backup = {
    enable = true;
    pre = ''
      dump="/tmp/authentik_db.sql"
      ${pkgs.docker}/bin/docker exec authentik_db sh -c "pg_dump -U authentik" > "$dump"
    '';
    post = ''rm -f "$dump"'';
    paths = ["/tmp/authentik_db.sql"];
    volumes = [
      "authentik_db"
      "authentik_redis"
      "authentik_templates"
      "authentik_certs"
      "authentik_media"
    ];
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
