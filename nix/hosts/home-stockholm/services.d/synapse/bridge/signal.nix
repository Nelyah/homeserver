# Signal bridge configuration module
# Returns {files, secretFiles} to be merged into the main synapse service
{...}: {
  files = {
    "signal-init-db.sh" = {
      source = ./signal-init-db.sh;
      destination = "signal/init-db.sh";
      executable = true;
    };
  };
  secretFiles = {
    "signal-config.yaml" = {
      destination = "signal/config.yaml";
      perms = "0600";
      mountable = true;
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-signal" -}}
        {{ $s := . -}}
        {{ with secret "homeserver_secrets/data/doublepuppet" -}}
        # Signal bridge configuration

        homeserver:
          address: http://synapse:8008
          domain: nelyah.eu
          software: standard

        appservice:
          address: http://mautrix-signal:29328
          hostname: 0.0.0.0
          port: 29328
          id: mautrix-signal
          ephemeral_events: true
          as_token: "{{ $s.Data.data.AS_TOKEN }}"
          hs_token: "{{ $s.Data.data.HS_TOKEN }}"
          bot:
            username: signalbot
            displayname: Signal Bridge Bot
            avatar: mxc://maunium.net/wPJgTQbZOtpBFmDNkiNEMDUp
          username_template: "signal_{{ "{{" }}.{{ "}}" }}"

        database:
          type: postgres
          uri: "postgres://mautrix_signal:{{ $s.Data.data.POSTGRES_PASSWORD }}@synapse_db/mautrix_signal?sslmode=disable"

        network:
          displayname_template: '{{ "{{" }}or .ContactName .ProfileName .PhoneNumber "Unknown"{{ "}}" }}'
          autocreate_contact_portal: true
          autocreate_group_portal: true
          use_contact_avatars: true
          sync_contacts_on_startup: true
          use_outdated_profiles: true

        backfill:
          enabled: true
          unread_hours_threshold: 72000

        bridge:
          contact_list_names: prefer
          command_prefix: "!signal"
          private_chat_portal_meta: true
          resend_bridge_info: true
          unknown_error_auto_reconnect: 1m
          permissions:
            "@nelyah:nelyah.eu": admin

        double_puppet:
          secrets:
            nelyah.eu: "as_token:{{ .Data.data.AS_TOKEN }}"
          servers:
            nelyah.eu: "http://synapse:8008"

        encryption:
          recovery_key: disable
          self_sign: true
          msc4190: true
          allow: true
          default: true
          require: false
          appservice: true
          allow_key_sharing: true
          pickle_key: "{{ $s.Data.data.PICKLE_KEY }}"
          verification_levels:
            receive: unverified
            send: unverified
            share: unverified
          rotation:
            enable_custom: true
            milliseconds: 604800000
            messages: 100
            disable_device_change_key_rotation: true

        public_media:
          signing_key: "{{ $s.Data.data.PUBLIC_MEDIA_SIGNING_KEY }}"

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

    # Signal bridge environment variables (only DB password for init container)
    "signal.env" = {
      destination = "signal/signal.env";
      perms = "0600";
      template = ''
        {{ with secret "homeserver_secrets/data/mautrix-signal" -}}
        MAUTRIX_POSTGRES_PASSWORD={{ .Data.data.POSTGRES_PASSWORD }}
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
