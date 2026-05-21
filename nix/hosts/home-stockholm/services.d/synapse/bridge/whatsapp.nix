# WhatsApp bridge configuration module
# Returns {files, secretFiles} to be merged into the main synapse service
{...}: {
  files = {
    "whatsapp-init-db.sh" = {
      source = ./whatsapp-init-db.sh;
      destination = "whatsapp/init-db.sh";
      executable = true;
    };
  };
  secretFiles = {
    "whatsapp-config.yaml" = {
      destination = "whatsapp/config.yaml";
      perms = "0600";
      mountable = true;
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-whatsapp" -}}
        {{ $s := . -}}
        {{ with secret "homeserver_secrets/data/doublepuppet" -}}
        # WhatsApp bridge configuration

        homeserver:
          address: http://synapse:8008
          domain: nelyah.eu
          software: standard
          async_media: true

        appservice:
          address: http://mautrix-whatsapp:29318
          hostname: 0.0.0.0
          port: 29318
          id: mautrix-whatsapp
          as_token: "{{ $s.Data.data.AS_TOKEN }}"
          hs_token: "{{ $s.Data.data.HS_TOKEN }}"
          bot:
            username: whatsappbot
            displayname: WhatsApp Bridge Bot
            avatar: mxc://maunium.net/NeXNQarUbrlYBiPCpprYsRqr
          username_template: "whatsapp_{{ "{{" }}.{{ "}}" }}"

        database:
          type: postgres
          uri: "postgres://mautrix_whatsapp:{{ $s.Data.data.POSTGRES_PASSWORD }}@synapse_db/mautrix_whatsapp?sslmode=disable"

        network:
          displayname_template: '{{ "{{" }}or .FullName .BusinessName .PushName .Phone .RedactedPhone "Unknown user"{{ "}}" }}'
          whatsapp_thumbnail: true
          url_previews: true
          history_sync:
            max_initial_conversations: -1
            request_full_sync: true

        matrix:
          delivery_receipt: true
          message_error_notices: true

        backfill:
          enabled: true
          unread_hours_threshold: 2160

        bridge:
          command_prefix: "!wa"
          private_chat_portal_meta: true
          permissions:
            "@nelyah:nelyah.eu": admin

        double_puppet:
          secrets:
            nelyah.eu: "as_token:{{ .Data.data.AS_TOKEN }}"
          servers:
            nelyah.eu: "http://synapse:8008"

        encryption:
          allow: true
          msc4190: true
          msc4392: true
          self_sign: true
          default: true
          require: false
          appservice: true
          allow_key_sharing: true
          pickle_key: "{{ $s.Data.data.PICKLE_KEY }}"

        provisioning:
          shared_secret: "{{ $s.Data.data.PROVISIONING_SECRET }}"

        logging:
          min_level: info
          writers:
            - type: stdout
              format: pretty-colored
        {{- end }}
        {{- end }}
      '';
    };

    # WhatsApp bridge environment variables (only DB password for init container)
    "whatsapp.env" = {
      destination = "whatsapp/whatsapp.env";
      perms = "0600";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-whatsapp" -}}
        MAUTRIX_POSTGRES_PASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
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
