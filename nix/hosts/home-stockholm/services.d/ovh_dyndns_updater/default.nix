{config, pkgs, lib, ...}: {
  name = "ovh_dyndns_updater";
  compose = {
    enable = false;
    build = true;
    networks = [];
    volumes = [];
  };
  files = {
    "Dockerfile".source = ./Dockerfile;
    "ovh-update-dyndns.py".source = ./ovh-update-dyndns.py;
    "requirements.txt".source = ./requirements.txt;
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
