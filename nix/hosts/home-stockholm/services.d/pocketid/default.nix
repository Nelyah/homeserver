{
  config,
  pkgs,
  lib,
  ...
}: {
  name = "pocketid";
  compose = {
    enable = true;
    networks = ["frontend" "pocketid"];
    volumes = ["pocketid_data" "tinyauth_data"];
  };
  secretFiles = {
    "pocketid.env" = {
      destination = "pocketid.env";
      template = ''
        {{ with secret "homeserver_secrets/data/pocketid" -}}
        # PocketID
        APP_URL=https://pocketid.nelyah.eu
        ENCRYPTION_KEY={{ .Data.data.ENCRYPTION_KEY }}
        TRUST_PROXY=true
        {{ end -}}
      '';
    };
    "tinyauth.env" = {
      destination = "tinyauth.env";
      template = ''
          {{ with secret "homeserver_secrets/data/tinyauth" -}}
          # TinyAuth
          TINYAUTH_APPURL=https://tinyauth.nelyah.eu
          TINYAUTH_AUTH_USERS={{ .Data.data.USER_PASSWD_HASH }}
          TINYAUTH_SECRET={{ .Data.data.SECRET }}
          TINYAUTH_OAUTH_AUTOREDIRECT=pocketid

          TINYAUTH_OAUTH_PROVIDERS_POCKETID_CLIENTID={{ .Data.data.POCKETID_CLIENT_ID }}
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_CLIENTSECRET={{ .Data.data.POCKETID_CLIENT_SECRET }}
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_AUTHURL=https://pocketid.nelyah.eu/authorize
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_TOKENURL=https://pocketid.nelyah.eu/api/oidc/token
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_USERINFOURL=https://pocketid.nelyah.eu/api/oidc/userinfo
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_REDIRECTURL=https://tinyauth.nelyah.eu/api/oauth/callback/pocketid
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_SCOPES=openid email profile groups
          TINYAUTH_OAUTH_PROVIDERS_POCKETID_NAME=Pocket ID
          {{ end -}}
      '';
    };
  };
  backup = {
    enable = true;
    needsServiceStopped = true;
    volumes = ["pocketid_data" "tinyauth_data"];
    tags = ["pocketid" "tinyauth"];
    policy = {
      daily = 10;
      weekly = 52;
    };
  };
}
