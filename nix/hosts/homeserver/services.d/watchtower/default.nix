{config, pkgs, lib, ...}: {
  name = "watchtower";
  compose = {
    enable = true;
    networks = ["watchtower"];
    volumes = [];
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/watchtower" -}}
        WATCHTOWER_API_TOKEN={{ .Data.data.API_TOKEN }}
        {{ end -}}
      '';
    };
  };
}
