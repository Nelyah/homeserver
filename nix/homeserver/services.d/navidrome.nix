{config, ...}: {
  name = "navidrome";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/navidrome/docker-compose.yml";
    networks = ["navidrome"];
    volumes = [
      "navidrome_data"
      "navidrome_mum_data"
    ];
  };
  backup = {
    enable = true;
    volumes = [
      "navidrome_data"
      "navidrome_mum_data"
    ];
  };
}
