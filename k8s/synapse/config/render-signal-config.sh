#!/bin/sh
set -eu

mkdir -p /runtime

yaml_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"
}

as_token_yaml="$(yaml_quote "$AS_TOKEN")"
hs_token_yaml="$(yaml_quote "$HS_TOKEN")"
pickle_key_yaml="$(yaml_quote "$PICKLE_KEY")"
public_media_signing_key_yaml="$(yaml_quote "$PUBLIC_MEDIA_SIGNING_KEY")"
provisioning_secret_yaml="$(yaml_quote "$PROVISIONING_SECRET")"
doublepuppet_secret_yaml="$(yaml_quote "as_token:$DOUBLEPUPPET_AS_TOKEN")"

cat > /runtime/config.yaml <<EOF
# Signal bridge configuration

homeserver:
  address: http://synapse
  domain: nelyah.eu
  software: standard

appservice:
  address: http://mautrix-signal:29328
  hostname: 0.0.0.0
  port: 29328
  id: mautrix-signal
  ephemeral_events: true
  as_token: $as_token_yaml
  hs_token: $hs_token_yaml
  bot:
    username: signalbot
    displayname: Signal Bridge Bot
    avatar: mxc://maunium.net/wPJgTQbZOtpBFmDNkiNEMDUp
  username_template: "signal_{{.}}"

database:
  type: postgres
  uri: "postgres://mautrix_signal:$POSTGRES_PASSWORD@synapse-db/mautrix_signal?sslmode=disable"

network:
  displayname_template: '{{or .ContactName .ProfileName .PhoneNumber "Unknown"}}'
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
    nelyah.eu: $doublepuppet_secret_yaml
  servers:
    nelyah.eu: "http://synapse"

encryption:
  recovery_key: disable
  self_sign: true
  msc4190: true
  allow: true
  default: true
  require: false
  appservice: true
  allow_key_sharing: true
  pickle_key: $pickle_key_yaml
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
  signing_key: $public_media_signing_key_yaml

provisioning:
  shared_secret: $provisioning_secret_yaml

logging:
  min_level: info
  writers:
    - type: stdout
      format: pretty-colored
EOF

chmod 0444 /runtime/config.yaml
