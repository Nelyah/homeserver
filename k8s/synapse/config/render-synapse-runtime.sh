#!/bin/sh
set -eu

mkdir -p /runtime/secrets /runtime/appservices

yaml_quote() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/'/''/g")"
}

printf '%s' "$REGISTRATION_SHARED_SECRET" > /runtime/secrets/registration_shared_secret

doublepuppet_as_token="$(yaml_quote "$DOUBLEPUPPET_AS_TOKEN")"
doublepuppet_hs_token="$(yaml_quote "$DOUBLEPUPPET_HS_TOKEN")"
signal_as_token="$(yaml_quote "$SIGNAL_AS_TOKEN")"
signal_hs_token="$(yaml_quote "$SIGNAL_HS_TOKEN")"
whatsapp_as_token="$(yaml_quote "$WHATSAPP_AS_TOKEN")"
whatsapp_hs_token="$(yaml_quote "$WHATSAPP_HS_TOKEN")"

cat > /runtime/appservices/doublepuppet.yaml <<EOF
id: doublepuppet
url:
as_token: $doublepuppet_as_token
hs_token: $doublepuppet_hs_token
sender_localpart: _doublepuppet_bot
rate_limited: false
namespaces:
  users:
    - regex: '@.*:nelyah\.eu$'
      exclusive: false
EOF

cat > /runtime/appservices/signal.yaml <<EOF
id: mautrix-signal
url: http://mautrix-signal:29328
as_token: $signal_as_token
hs_token: $signal_hs_token
sender_localpart: signalbot
rate_limited: false
push_ephemeral: true
de.sorunome.msc2409.push_ephemeral: true
org.matrix.msc3202: true
namespaces:
  users:
    - regex: '^@signal_.*:nelyah\.eu$'
      exclusive: true
    - regex: '^@signalbot:nelyah\.eu$'
      exclusive: true
  aliases:
    - regex: '^#signal_.*:nelyah\.eu$'
      exclusive: true
EOF

cat > /runtime/appservices/whatsapp.yaml <<EOF
id: mautrix-whatsapp
url: http://mautrix-whatsapp:29318
as_token: $whatsapp_as_token
hs_token: $whatsapp_hs_token
sender_localpart: whatsappbot
rate_limited: false
push_ephemeral: true
de.sorunome.msc2409.push_ephemeral: true
org.matrix.msc3202: true
namespaces:
  users:
    - regex: '^@whatsapp_.*:nelyah\.eu$'
      exclusive: true
    - regex: '^@whatsappbot:nelyah\.eu$'
      exclusive: true
  aliases:
    - regex: '^#whatsapp_.*:nelyah\.eu$'
      exclusive: true
EOF

chown -R 991:991 /runtime
chmod 0500 /runtime/secrets /runtime/appservices
chmod 0400 /runtime/secrets/registration_shared_secret /runtime/appservices/*.yaml
