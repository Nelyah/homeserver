{config, ...}: {
  name = "watchtower";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/watchtower/docker-compose.yml";
    networks = ["watchtower"];
    volumes = [];
  };
}
