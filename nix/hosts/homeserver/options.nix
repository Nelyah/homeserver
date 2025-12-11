{lib, ...}: let
  inherit (lib) mkOption types;
in {
  options.homeserver = {
    mainDrive = mkOption {
      type = types.str;
      default = "/data";
      description = "Mount point for main data drive.";
    };

    backupDrive = mkOption {
      type = types.str;
      default = "/data2";
      description = "Mount point for backup drive.";
    };

    homeserverRoot = mkOption {
      type = types.str;
      default = "/data/homeserver";
      description = "Root path of the homeserver repo on the host.";
    };

    vault.address = mkOption {
      type = types.str;
      default = "https://vault.nelyah.eu";
      description = "Vault address for the Vault agent.";
    };

    vault.tokenPath = mkOption {
      type = types.str;
      default = "/data/homeserver/ansible/.vault-token";
      description = "Path to Vault token used by the Vault agent (read-only).";
    };

    vault.unsealTokenPath = mkOption {
      type = types.str;
      default = "/data/homeserver/ansible/.vault-unseal-token";
      description = "Path to Vault token used to unseal Vault (read-only).";
    };

    vault.secrets = mkOption {
      type = types.attrsOf (types.submodule {
        options = {
          template = mkOption {
            type = types.str;
            description = "Vault template content (Consul Template syntax).";
          };
          destination = mkOption {
            type = types.str;
            description = "Path relative to /var/lib/secrets/ (e.g., 'restic/local.env').";
          };
          perms = mkOption {
            type = types.str;
            default = "0400";
            description = "File permissions (octal string).";
          };
        };
      });
      default = {};
      description = "Vault secrets to be rendered by vault-agent under /var/lib/secrets/. All secrets are owned by root.";
    };
  };
}
