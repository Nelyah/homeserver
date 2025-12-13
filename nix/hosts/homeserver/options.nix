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
      default = "/var/lib/secrets/vault/access-token";
      description = "Path to Vault token used by the Vault agent (read-only).";
    };

    vault.unsealTokenPath = mkOption {
      type = types.str;
      default = "/var/lib/secrets/vault/unseal-token";
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
            description = "Path relative to homeserver.paths.secretsRoot (e.g., 'restic/local.env').";
          };
          perms = mkOption {
            type = types.str;
            default = "0400";
            description = "File permissions (octal string).";
          };
        };
      });
      default = {};
      description = "Vault secrets to be rendered by vault-agent under homeserver.paths.secretsRoot. All secrets are owned by root.";
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
            type = types.nullOr (types.submodule ({config, ...}: let
              backupCfg = config;
            in {
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
                needsServiceStopped = mkOption {
                  type = types.bool;
                  default = false;
                  description = "Stop the service's docker-compose systemd unit before backing up volumes/paths (recommended for database volumes).";
                };
                tags = mkOption {
                  type = types.listOf types.str;
                  default = [];
                  apply = tags: if tags == [] then [cfg.name] else tags;
                  description = "Restic tags (defaults to service name when unset).";
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

                restore = mkOption {
                  type = types.nullOr (types.submodule ({...}: {
                    options = {
                      tag = mkOption {
                        type = types.str;
                        default = cfg.name;
                        description = "Restic tag used to select the latest snapshot for this service.";
                      };

                      volumes = mkOption {
                        type = types.listOf types.str;
                        default = backupCfg.volumes;
                        description = "Docker volumes to restore (defaults to backup.volumes).";
                      };

                      paths = mkOption {
                        type = types.listOf types.str;
                        default = backupCfg.paths;
                        description = "File paths to restore (defaults to backup.paths).";
                      };

                      stopCompose = mkOption {
                        type = types.bool;
                        default = cfg.compose != null && (cfg.compose.enable or false);
                        description = "Stop/start the docker-compose systemd unit around restore.";
                      };

                      composeUnit = mkOption {
                        type = types.nullOr types.str;
                        default = null;
                        description = "Systemd unit name to stop/start when stopCompose is enabled (defaults to docker-compose-<service>.service).";
                      };

                      restic = mkOption {
                        type = types.submodule {
                          options = {
                            target = mkOption {
                              type = types.str;
                              default = "/";
                              description = "Target directory passed to `restic restore --target`.";
                            };
                          };
                        };
                        default = {};
                        description = "Restic restore options.";
                      };
                    };
                  }));
                  default = {};
                  description = "Restore configuration for this service.";
                };
              };
            }));
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
