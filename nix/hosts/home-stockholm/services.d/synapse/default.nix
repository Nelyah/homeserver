{...}: {
  name = "synapse";
  backup = {
    enable = true;
    kubernetes = {
      namespace = "synapse";
      deployments = ["mautrix-signal" "mautrix-whatsapp" "synapse" "synapse-db"];
      pvcs = [
        "synapse-db"
        "synapse-data"
        "mautrix-signal-data"
        "mautrix-whatsapp-data"
      ];
    };
    tags = ["synapse"];
    exclude = [
      "*.log"
      "*.log.*"
      "media_store/url_cache*"
    ];
    policy = {
      daily = 30;
      weekly = 4;
    };
  };
}
