{ pkgs, config, ... }:
let
  # Flow: Vault compose stack starts → vault-agent renders secrets from external Vault
  # into /run/secrets → unseal unit reads unseal token and unseals the Vault container.
  vaultComposeService = "docker-compose-vault.service";

  agentConfig = pkgs.writeText "vault-agent.hcl" ''
    exit_after_auth = false
    pid_file = "/run/vault-agent.pid"

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
      destination = "/run/secrets/restic/local.env"
      perms = "0400"
    }

    template {
      source      = "/etc/vault-agent-templates/restic-remote.ctmpl"
      destination = "/run/secrets/restic/remote.env"
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
in
{
  environment.etc = {
    "vault-agent.hcl".source = agentConfig;
    "vault-agent-templates/restic-local.ctmpl".source = resticLocalTemplate;
    "vault-agent-templates/restic-remote.ctmpl".source = resticRemoteTemplate;
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
      ReadWritePaths = [
        "/run/secrets"
        "/run/vault-agent.pid"
      ];
    ReadOnlyPaths = [ "${config.homeserver.vault.tokenPath}" ];
      Restart = "on-failure";
      RestartSec = "10s";
    };
  };

  # Enforce strict permissions on vault tokens if they exist on disk.
  systemd.tmpfiles.rules = [
    # z: restore the mode/ownership if the file exists (do not create if absent).
    "z ${config.homeserver.vault.tokenPath} 0400 root root -"
    "z ${config.homeserver.vault.unsealTokenPath} 0400 root root -"
  ];
}
