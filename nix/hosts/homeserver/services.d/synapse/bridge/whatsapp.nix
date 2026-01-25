# WhatsApp bridge configuration module
# Returns {files, secretFiles} to be merged into the main synapse service
{...}: {
  files = {
    "whatsapp-config.yaml" = {
      source = ./whatsapp-config.yaml;
      destination = "whatsapp/config.yaml";
    };
    "whatsapp-init-db.sh" = {
      source = ./whatsapp-init-db.sh;
      destination = "whatsapp/init-db.sh";
      executable = true;
    };
  };
  secretFiles = {
    # WhatsApp bridge environment variables (secrets injected via env vars)
    "whatsapp.env" = {
      destination = "whatsapp/whatsapp.env";
      perms = "0600";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-whatsapp" -}}
        BRIDGE_appservice__as_token={{ .Data.data.AS_TOKEN }}
        BRIDGE_appservice__hs_token={{ .Data.data.HS_TOKEN }}
        BRIDGE_database__uri=postgres://mautrix_whatsapp:{{ .Data.data.POSTGRES_PASSWORD }}@synapse_db/mautrix_whatsapp?sslmode=disable
        BRIDGE_encryption__pickle_key={{ .Data.data.PICKLE_KEY }}
        BRIDGE_provisioning__shared_secret={{ .Data.data.PROVISIONING_SECRET }}
        MAUTRIX_POSTGRES_PASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
        {{- end }}
        {{ with secret "homeserver_secrets/data/doublepuppet" -}}
        BRIDGE_double_puppet__secrets__nelyah.eu=as_token:{{ .Data.data.AS_TOKEN }}
        {{- end }}
      '';
    };

    # WhatsApp bridge registration for Synapse
    "whatsapp-registration.yaml" = {
      destination = "appservices/whatsapp.yaml";
      perms = "0600";
      mountable = true;
      owner = "991:991";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-whatsapp" -}}
        id: mautrix-whatsapp
        url: http://mautrix-whatsapp:29318
        as_token: "{{ .Data.data.AS_TOKEN }}"
        hs_token: "{{ .Data.data.HS_TOKEN }}"
        sender_localpart: whatsappbot
        rate_limited: false
        push_ephemeral: true
        de.sorunome.msc2409.push_ephemeral: true
        org.matrix.msc3202: true
        namespaces:
          users:
            - regex: "^@whatsapp_.*:nelyah\\.eu$"
              exclusive: true
            - regex: "^@whatsappbot:nelyah\\.eu$"
              exclusive: true
          aliases:
            - regex: "^#whatsapp_.*:nelyah\\.eu$"
              exclusive: true
        {{ end -}}
      '';
    };
  };
}
