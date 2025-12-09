{config, ...}: {
  name = "ovh_dyndns_updater";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/ovh_dyndns_updater/docker-compose.yml";
    networks = [];
    volumes = [];
  };
}
