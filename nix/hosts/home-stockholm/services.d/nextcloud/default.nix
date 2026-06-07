{...}: {
  name = "nextcloud";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "nextcloud";
      deployments = ["nextcloud-cron" "nextcloud" "redis" "mariadb-nc"];
      pvcs = [
        "nextcloud-mariadb"
        "nextcloud-data"
        "nextcloud-site"
        "nextcloud-redis-data"
      ];
    };
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
