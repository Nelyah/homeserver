# Signal bridge configuration module
# Returns {files, secretFiles} to be merged into the main synapse service
{...}: {
  files = {
    "signal-config.yaml" = {
      source = ./signal-config.yaml;
      destination = "signal/config.yaml";
    };
    "signal-init-db.sh" = {
      source = ./signal-init-db.sh;
      destination = "signal/init-db.sh";
      executable = true;
    };
  };
  secretFiles = {
    # Signal bridge environment variables (secrets injected via env vars)
    "signal.env" = {
      destination = "signal/signal.env";
      perms = "0600";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-signal" -}}
        BRIDGE_appservice__as_token={{ .Data.data.AS_TOKEN }}
        BRIDGE_appservice__hs_token={{ .Data.data.HS_TOKEN }}
        BRIDGE_database__uri=postgres://mautrix_signal:{{ .Data.data.POSTGRES_PASSWORD }}@synapse_db/mautrix_signal?sslmode=disable
        BRIDGE_encryption__pickle_key={{ .Data.data.PICKLE_KEY }}
        BRIDGE_public_media__signing_key={{ .Data.data.PUBLIC_MEDIA_SIGNING_KEY }}
        BRIDGE_provisioning__shared_secret={{ .Data.data.PROVISIONING_SECRET }}
        MAUTRIX_POSTGRES_PASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
        {{- end }}
        {{ with secret "homeserver_secrets/data/doublepuppet" -}}
        BRIDGE_double_puppet__secrets__nelyah.eu=as_token:{{ .Data.data.AS_TOKEN }}
        {{- end }}
      '';
    };

    # Signal bridge registration for Synapse
    "signal-registration.yaml" = {
      destination = "appservices/signal.yaml";
      perms = "0600";
      mountable = true;
      owner = "991:991";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-signal" -}}
        id: mautrix-signal
        url: http://mautrix-signal:29328
        as_token: "{{ .Data.data.AS_TOKEN }}"
        hs_token: "{{ .Data.data.HS_TOKEN }}"
        sender_localpart: signalbot
        rate_limited: false
        push_ephemeral: true
        de.sorunome.msc2409.push_ephemeral: true
        org.matrix.msc3202: true
        namespaces:
          users:
            - regex: "^@signal_.*:nelyah\\.eu$"
              exclusive: true
            - regex: "^@signalbot:nelyah\\.eu$"
              exclusive: true
          aliases:
            - regex: "^#signal_.*:nelyah\\.eu$"
              exclusive: true
        {{ end -}}
      '';
    };
  };
}
