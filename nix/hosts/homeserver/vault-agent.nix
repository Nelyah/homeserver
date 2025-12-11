{
  pkgs,
  config,
  ...
}: let
  # Flow: Vault compose stack starts → vault-agent renders secrets from external Vault
  # into /var/lib/secrets → unseal unit reads unseal token and unseals the Vault container.
  vaultComposeService = "docker-compose-vault.service";

  agentConfig = pkgs.writeText "vault-agent.hcl" ''
    exit_after_auth = false
    pid_file = "/run/vault-agent/pid"

    auto_auth {
      method "token_file" {
        config = {
          token_file_path = "${config.homeserver.vault.tokenPath}"
          token_period = "24h"
        }
      }
      sink "file" {
        config = {
          path = "/run/vault-agent/token"
        }
      }
    }

    template {
      source      = "/etc/vault-agent-templates/restic-local.ctmpl"
      destination = "/var/lib/secrets/restic/local.env"
      perms = "0400"
    }

    template {
      source      = "/etc/vault-agent-templates/restic-remote.ctmpl"
      destination = "/var/lib/secrets/restic/remote.env"
      perms = "0400"
    }

    template {
      source      = "/etc/vault-agent-templates/pushover.ctmpl"
      destination = "/var/lib/secrets/pushover.env"
      perms = "0400"
    }

    template {
      source      = "/etc/vault-agent-templates/frp-token.ctmpl"
      destination = "/var/lib/secrets/frp-token"
      perms = "0400"
    }
  '';

  resticLocalTemplate = pkgs.writeText "restic-local.ctmpl" ''
    {{ with secret "homeserver_secrets/data/restic" -}}
    RESTIC_PASSWORD={{ .Data.data.LOCAL_PASSWD }}
    RESTIC_REPOSITORY=${config.homeserver.backupDrive}/backups
    {{ end -}}
  '';

  resticRemoteTemplate = pkgs.writeText "restic-remote.ctmpl" ''
    {{ with secret "homeserver_secrets/data/restic" -}}
    RESTIC_PASSWORD={{ .Data.data.REMOTE_PASSWD }}
    RESTIC_REPOSITORY={{ .Data.data.REMOTE_ADDR }}:/home/chloe/USB/backups
    {{ end -}}
  '';

  pushoverTemplate = pkgs.writeText "pushover.ctmpl" ''
    {{ with secret "homeserver_secrets/data/pushover" -}}
    PUSHOVER_TOKEN={{ .Data.data.PUSHOVER_TOKEN }}
    PUSHOVER_USER={{ .Data.data.PUSHOVER_USER }}
    {{ end -}}
  '';

  frpTokenTemplate = pkgs.writeText "frp-token.ctmpl" ''
    {{ with secret "homeserver_secrets/data/frp" -}}
    {{ .Data.data.token }}
    {{ end -}}
  '';
in {
  environment.etc = {
    "vault-agent.hcl".source = agentConfig;
    "vault-agent-templates/restic-local.ctmpl".source = resticLocalTemplate;
    "vault-agent-templates/restic-remote.ctmpl".source = resticRemoteTemplate;
    "vault-agent-templates/pushover.ctmpl".source = pushoverTemplate;
    "vault-agent-templates/frp-token.ctmpl".source = frpTokenTemplate;
  };

  systemd.services.vault-agent = {
    description = "Vault Agent for homeserver secrets";
    after = [
      "network-online.target"
      vaultComposeService
    ];
    wants = [
      "network-online.target"
      vaultComposeService
    ];
    serviceConfig = {
      Type = "simple";
      ExecStart = "${pkgs.vault}/bin/vault agent -config /etc/vault-agent.hcl";
      Environment = "VAULT_ADDR=${config.homeserver.vault.address}";
      User = "root";
      Group = "root";
      RuntimeDirectory = "vault-agent";
      ReadWritePaths = [
        "/var/lib/secrets"
        "/run/vault-agent"
      ];
      ReadOnlyPaths = ["${config.homeserver.vault.tokenPath}"];
      Restart = "on-failure";
      RestartSec = "10s";
    };
  };

  # Enforce strict permissions on vault tokens if they exist on disk.
  systemd.tmpfiles.rules = [
    "d /var/lib/secrets 0700 root root -"
    "d /var/lib/secrets/restic 0700 root root -"
    # z: restore the mode/ownership if the file exists (do not create if absent).
    "z ${config.homeserver.vault.tokenPath} 0400 root root -"
    "z ${config.homeserver.vault.unsealTokenPath} 0400 root root -"
    "z /var/lib/secrets/frp-token 0400 root root -"
  ];
}
