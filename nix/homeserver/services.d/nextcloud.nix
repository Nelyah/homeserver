{config, ...}: {
  name = "nextcloud";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/nextcloud/docker-compose.yml";
    networks = ["nextcloud"];
    volumes = [
      "nextcloud_data"
      "nextcloud_site"
      "nextcloud_mariadb"
      "nextcloud_redis_data"
    ];
  };
  backup = {
    enable = true;
    pre = ''
      dump="/tmp/nextcloud_db.sql"
      docker exec -u www-data nextcloud php /var/www/html/occ maintenance:mode --on
      docker exec mariadb-nc sh -c "exec mariadb-dump -u root -p$MYSQL_ROOT_PASSWORD ${"$"}{NEXTCLOUD_DB:-nextcloud}" > "$dump"
    '';
    post = ''
      docker exec -u www-data nextcloud php /var/www/html/occ maintenance:mode --off
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
