{config, pkgs, lib, ...}: {
  name = "authentik";
  compose = {
    enable = true;
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
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/authentik" -}}
        POSTGRES_DB=authentik
        POSTGRES_USER=authentik
        POSTGRES_PASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
        AUTHENTIK_SECRET_KEY={{ .Data.data.AUTHENTIK_SECRET_KEY }}
        {{ end -}}
      '';
    };
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
