{config, lib, ...}: let
  signalBridge = import ./bridge/signal.nix {inherit config lib;};
  whatsappBridge = import ./bridge/whatsapp.nix {inherit config lib;};
in {
  name = "synapse";
  compose = {
    enable = true;
    networks = ["synapse"];
    volumes = [
      "synapse_data"
      "synapse_db"
      "mautrix_signal_data"
      "mautrix_whatsapp_data"
    ];
  };
  files = {
    "log.config".source = ./log.config;
    "homeserver.yaml".source = ./homeserver.yaml;
  } // signalBridge.files // whatsappBridge.files;
  secretFiles = {
    "synapse.env" = {
      destination = "synapse.env";
      template = ''
        SYNAPSE_CONFIG_PATH=/run/var/homeserver.yaml
        TZ=Europe/Stockholm
        {{ with secret "homeserver_secrets/data/synapse" -}}
        PGPASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
        {{- end }}
      '';
    };
    "registration_shared_secret" = {
      destination = "secrets/registration_shared_secret";
      perms = "0600";
      mountable = true;
      owner = "991:991";
      template = ''{{ with secret "homeserver_secrets/data/synapse" }}{{ .Data.data.REGISTRATION_SHARED_SECRET }}{{ end }}'';
    };
    "postgres.env" = {
      destination = "postgres.env";
      template = ''
        POSTGRES_USER=synapse
        POSTGRES_DB=synapse
        POSTGRES_INITDB_ARGS=--encoding=UTF-8 --lc-collate=C --lc-ctype=C
        {{ with secret "homeserver_secrets/data/synapse" -}}
        POSTGRES_PASSWORD="{{ .Data.data.POSTGRES_PASSWORD }}"
        {{- end }}
      '';
    };
    # Double puppeting appservice registration (shared by all bridges)
    "doublepuppet.yaml" = {
      destination = "appservices/doublepuppet.yaml";
      perms = "0600";
      mountable = true;
      owner = "991:991";
      template = ''
        {{ with secret "homeserver_secrets/data/doublepuppet" -}}
        id: doublepuppet
        url:
        as_token: "{{ .Data.data.AS_TOKEN }}"
        hs_token: "{{ .Data.data.HS_TOKEN }}"
        sender_localpart: _doublepuppet_bot
        rate_limited: false
        namespaces:
          users:
            - regex: "@.*:nelyah\\.eu$"
              exclusive: false
        {{ end -}}
      '';
    };
  } // signalBridge.secretFiles // whatsappBridge.secretFiles;
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = [
      "synapse_db"
      "synapse_data"
      "mautrix_signal_data"
      "mautrix_whatsapp_data"
    ];
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
