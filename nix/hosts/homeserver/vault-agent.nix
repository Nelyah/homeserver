{
  pkgs,
  config,
  lib,
  ...
}: let
  secretsRoot = config.homeserver.paths.secretsRoot;
  vaultComposeService = "docker-compose-vault.service";
  secrets = config.homeserver.vault.secrets;

  # Build absolute paths from relative destinations
  secretPaths = lib.mapAttrs (_: s: "${secretsRoot}/${s.destination}") secrets;

  # Generate template files from declarations
  templateFiles = lib.mapAttrs (name: secret:
    pkgs.writeText "${name}.ctmpl" secret.template
  ) secrets;

  # Generate HCL template blocks (using absolute paths)
  templateBlocks = lib.concatStringsSep "\n\n" (
    lib.mapAttrsToList (name: secret: ''
      template {
        source      = "/etc/vault-agent-templates/${name}.ctmpl"
        destination = "${secretsRoot}/${secret.destination}"
        perms       = "${secret.perms}"
      }
    '') secrets
  );

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

    ${templateBlocks}
  '';

  # List of expected secret files (for cleanup script)
  expectedFiles = lib.attrValues secretPaths;

  # Cleanup script: remove files in secretsRoot not in current config
  cleanupScript = pkgs.writeShellScript "vault-secrets-cleanup" ''
    set -euo pipefail
    SECRETS_ROOT="${secretsRoot}"
    EXPECTED_FILES=(${lib.concatStringsSep " " (map (f: ''"${f}"'') expectedFiles)})

    # Find all files in secrets root
    while IFS= read -r -d "" file; do
      # Check if file is in expected list
      found=0
      for expected in "''${EXPECTED_FILES[@]}"; do
        if [[ "$file" == "$expected" ]]; then
          found=1
          break
        fi
      done
      # Remove if not expected (stale secret)
      if [[ $found -eq 0 ]]; then
        echo "Removing stale secret: $file"
        rm -f "$file"
      fi
    done < <(${pkgs.findutils}/bin/find "$SECRETS_ROOT" -type f -print0 2>/dev/null || true)
  '';

  # Auto-generate tmpfiles rules for parent directories
  secretDirs = lib.unique (
    lib.filter (d: d != secretsRoot) (
      map (path: builtins.dirOf path) (lib.attrValues secretPaths)
    )
  );
in
  lib.mkIf (secrets != {}) {
    environment.etc =
      {
        "vault-agent.hcl".source = agentConfig;
      }
      // lib.mapAttrs' (name: file: {
        name = "vault-agent-templates/${name}.ctmpl";
        value.source = file;
      })
      templateFiles;

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
        ExecStartPre = "${cleanupScript}";
        ExecStart = "${pkgs.vault}/bin/vault agent -config /etc/vault-agent.hcl";
        Environment = "VAULT_ADDR=${config.homeserver.vault.address}";
        User = "root";
        Group = "root";
        RuntimeDirectory = "vault-agent";
        ReadWritePaths = [
          secretsRoot
          "/run/vault-agent"
        ];
        ReadOnlyPaths = ["${config.homeserver.vault.tokenPath}"];
        Restart = "on-failure";
        RestartSec = "10s";
      };
    };

    systemd.tmpfiles.rules =
      [
        "d ${secretsRoot} 0700 root root -"
        # z: restore the mode/ownership if the file exists (do not create if absent).
        "z ${config.homeserver.vault.tokenPath} 0400 root root -"
        "z ${config.homeserver.vault.unsealTokenPath} 0400 root root -"
      ]
      ++ map (dir: "d ${dir} 0700 root root -") secretDirs;
  }
