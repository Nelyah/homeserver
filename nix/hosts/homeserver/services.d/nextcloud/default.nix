{config, pkgs, lib, ...}: {
  name = "nextcloud";
  compose = {
    enable = true;
    networks = ["nextcloud"];
    volumes = [
      "nextcloud_data"
      "nextcloud_site"
      "nextcloud_mariadb"
      "nextcloud_redis_data"
    ];
  };
  files = {
    "mariadb.conf".source = ./mariadb.conf;
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/nextcloud" -}}
        MYSQL_ROOT_PASSWORD={{ .Data.data.MYSQL_ROOT_PASSWORD }}
        MYSQL_DATABASE={{ .Data.data.MYSQL_DATABASE }}
        MYSQL_USER={{ .Data.data.MYSQL_USER }}
        MYSQL_PASSWORD={{ .Data.data.MYSQL_PASSWORD }}
        {{ end -}}
        NC_DATA_DIR=/data
        NC_WEBSITE_DIR=/var/www/html
      '';
    };
  };
  backup = {
    enable = true;
    pre = ''
      dump="/tmp/nextcloud_db.sql"
      ${pkgs.docker}/bin/docker exec -u www-data nextcloud php /var/www/html/occ maintenance:mode --on
      ${pkgs.docker}/bin/docker exec mariadb-nc sh -c "exec mariadb-dump -u root -p$MYSQL_ROOT_PASSWORD ${"$"}{NEXTCLOUD_DB:-nextcloud}" > "$dump"
    '';
    post = ''
      ${pkgs.docker}/bin/docker exec -u www-data nextcloud php /var/www/html/occ maintenance:mode --off
      rm -f "$dump"
    '';
    paths = ["/tmp/nextcloud_db.sql"];
    volumes = [
      "nextcloud_mariadb"
      "nextcloud_data"
      "nextcloud_site"
    ];
    tags = ["nextcloud"];
    exclude = [
      ".opcache"
      "access.log"
      "error.log"
      "nextcloud.log"
      "ncp-update-backups"
    ];
    policy = {
      daily = 90;
      weekly = 4;
    };
  };
}
