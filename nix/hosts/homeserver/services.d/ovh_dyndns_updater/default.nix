{config, pkgs, lib, ...}: {
  name = "ovh_dyndns_updater";
  compose = {
    enable = true;
    build = true;
    networks = [];
    volumes = [];
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/ovh_api" -}}
        OVH_APPLICATION_KEY={{ .Data.data.APPLICATION_KEY }}
        OVH_APPLICATION_SECRET={{ .Data.data.APPLICATION_SECRET }}
        OVH_CONSUMER_KEY={{ .Data.data.CONSUMER_KEY }}
        {{ end -}}
      '';
    };
  };
}
