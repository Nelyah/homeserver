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
          APP_URL=https://tinyauth.nelyah.eu
          USERS={{ .Data.data.USER_PASSWD_HASH }}
          TINYAUTH_SECRET={{ .Data.data.SECRET }}
          OAUTH_AUTO_REDIRECT=pocketid
          PROVIDERS_POCKETID_CLIENT_ID={{ .Data.data.POCKETID_CLIENT_ID }}
          PROVIDERS_POCKETID_CLIENT_SECRET={{ .Data.data.POCKETID_CLIENT_SECRET }}
          PROVIDERS_POCKETID_AUTH_URL=https://pocketid.nelyah.eu/authorize
          PROVIDERS_POCKETID_TOKEN_URL=https://pocketid.nelyah.eu/api/oidc/token
          PROVIDERS_POCKETID_USER_INFO_URL=https://pocketid.nelyah.eu/api/oidc/userinfo
          PROVIDERS_POCKETID_REDIRECT_URL=https://tinyauth.nelyah.eu/api/oauth/callback/pocketid
          PROVIDERS_POCKETID_SCOPES=openid email profile groups
          PROVIDERS_POCKETID_NAME=Pocket ID
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
