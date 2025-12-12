# Options can be imported standalone (by services.nix for validation)
# or as a NixOS module (by default.nix). When imported standalone,
# config is empty and the config block is skipped.
{lib, config ? {}, ...}: let
  inherit (lib) mkOption mkDefault types mkIf;
  # Check if we're being used as a NixOS module (config.homeserver exists)
  isNixOSModule = config ? homeserver;
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

    # Centralized path configuration
    paths = {
      deployRoot = mkOption {
        type = types.str;
        default = "/var/lib/docker-services";
        description = "Root directory for deployed docker service files.";
      };

      secretsRoot = mkOption {
        type = types.str;
        default = "/var/lib/secrets";
        description = "Root directory for vault-rendered secrets.";
      };

      dockerDataRoot = mkOption {
        type = types.str;
        description = "Docker data root directory.";
      };

      dockerVolumesRoot = mkOption {
        type = types.str;
        description = "Docker volumes directory.";
      };
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

    services = mkOption {
      description = "Service metadata defined in hosts/homeserver/services.d";
      default = {};
      type = types.attrsOf (types.submodule ({name, config, ...}: let
        cfg = config;
      in {
        options = {
          name = mkOption {
            type = types.str;
            default = name;
            description = "Service name (defaults to the attribute name).";
          };
          compose = mkOption {
            type = types.nullOr (types.submodule {
              options = {
                enable = mkOption {
                  type = types.bool;
                  default = false;
                  description = "Enable docker-compose for this service.";
                };
                path = mkOption {
                  type = types.nullOr types.str;
                  default = null;
                  description = "Path to docker-compose.yml; null to auto-derive /var/lib/docker-services/<name>/docker-compose.yml.";
                };
                networks = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  description = "External docker networks used by the service.";
                };
                volumes = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  description = "External docker volumes used by the service.";
                };
                build = mkOption {
                  type = types.bool;
                  default = false;
                  description = "Run docker-compose with --build.";
                };
              };
            });
            default = null;
            description = "Compose configuration for the service.";
          };
          files = mkOption {
            type = types.attrsOf (types.submodule {
              options = {
                source = mkOption {
                  type = types.path;
                  description = "Source file or directory to deploy.";
                };
                destination = mkOption {
                  type = types.nullOr types.str;
                  default = null;
                  description = "Destination relative path; null uses the attribute name.";
                };
                executable = mkOption {
                  type = types.bool;
                  default = false;
                  description = "Mark the deployed file as executable.";
                };
              };
            });
            default = {};
            description = "Files/directories to deploy for the service.";
          };
          secretFiles = mkOption {
            type = types.attrsOf (types.submodule {
              options = {
                template = mkOption {
                  type = types.str;
                  description = "Vault template content for the secret file.";
                };
                destination = mkOption {
                  type = types.str;
                  description = "Destination path relative to the service deploy dir.";
                };
                perms = mkOption {
                  type = types.str;
                  default = "0400";
                  description = "Permissions to set on rendered secret file.";
                };
              };
            });
            default = {};
            description = "Secret files rendered by Vault and symlinked into the service directory.";
          };
          backup = mkOption {
            type = types.nullOr (types.submodule {
              options = {
                enable = mkOption {
                  type = types.bool;
                  default = false;
                  description = "Enable backups for this service.";
                };
                paths = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  description = "File paths to back up.";
                };
                volumes = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  description = "Docker volumes to back up.";
                };
                tags = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  apply = tags: if tags == [] then [cfg.name] else tags;
                  description = "Restic tags (defaults to service name when unset).";
                };
                pre = mkOption {
                  type = types.str;
                  default = "";
                  description = "Pre-backup hook script.";
                };
                post = mkOption {
                  type = types.str;
                  default = "";
                  description = "Post-backup hook script.";
                };
                exclude = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  description = "Exclude patterns for backups.";
                };
                policy = mkOption {
                  type = types.nullOr (types.submodule {
                    options = {
                      last = mkOption {type = types.nullOr types.int; default = null;};
                      hourly = mkOption {type = types.nullOr types.int; default = null;};
                      daily = mkOption {type = types.nullOr types.int; default = 10;};
                      weekly = mkOption {type = types.nullOr types.int; default = 4;};
                      monthly = mkOption {type = types.nullOr types.int; default = 4;};
                      yearly = mkOption {type = types.nullOr types.int; default = null;};
                    };
                  });
                  default = {
                    daily = 10;
                    weekly = 4;
                    monthly = 4;
                  };
                  description = "Retention policy for backups (set to null to skip forget).";
                };
              };
            });
            default = null;
            description = "Backup configuration for the service.";
          };
        };
      }));
    };
  };

  # Set computed defaults for path options (only when used as NixOS module)
  config = mkIf isNixOSModule {
    homeserver.paths = {
      dockerDataRoot = mkDefault "${config.homeserver.mainDrive}/docker-data";
      dockerVolumesRoot = mkDefault "${config.homeserver.paths.dockerDataRoot}/volumes";
    };
  };
}
