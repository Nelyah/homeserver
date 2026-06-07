#!/bin/sh
set -eu

mkdir -p /runtime

yaml_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"
}

as_token_yaml="$(yaml_quote "$AS_TOKEN")"
hs_token_yaml="$(yaml_quote "$HS_TOKEN")"
pickle_key_yaml="$(yaml_quote "$PICKLE_KEY")"
provisioning_secret_yaml="$(yaml_quote "$PROVISIONING_SECRET")"
doublepuppet_secret_yaml="$(yaml_quote "as_token:$DOUBLEPUPPET_AS_TOKEN")"

cat > /runtime/config.yaml <<EOF
# WhatsApp bridge configuration

homeserver:
  address: http://synapse
  domain: nelyah.eu
  software: standard
  async_media: true

appservice:
  address: http://mautrix-whatsapp:29318
  hostname: 0.0.0.0
  port: 29318
  id: mautrix-whatsapp
  as_token: $as_token_yaml
  hs_token: $hs_token_yaml
  bot:
    username: whatsappbot
    displayname: WhatsApp Bridge Bot
    avatar: mxc://maunium.net/NeXNQarUbrlYBiPCpprYsRqr
  username_template: "whatsapp_{{.}}"

database:
  type: postgres
  uri: "postgres://mautrix_whatsapp:$POSTGRES_PASSWORD@synapse-db/mautrix_whatsapp?sslmode=disable"

network:
  displayname_template: '{{or .FullName .BusinessName .PushName .Phone .RedactedPhone "Unknown user"}}'
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
    nelyah.eu: $doublepuppet_secret_yaml
  servers:
    nelyah.eu: "http://synapse"

encryption:
  allow: true
  msc4190: true
  msc4392: true
  self_sign: true
  default: true
  require: false
  appservice: true
  allow_key_sharing: true
  pickle_key: $pickle_key_yaml

provisioning:
  shared_secret: $provisioning_secret_yaml

logging:
  min_level: info
  writers:
    - type: stdout
      format: pretty-colored
EOF

chmod 0444 /runtime/config.yaml
