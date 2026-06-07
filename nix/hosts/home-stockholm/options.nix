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

    paths = {
      secretsRoot = mkOption {
        type = types.str;
        default = "/var/lib/secrets";
        description = "Root directory for vault-rendered secrets.";
      };

      dockerDataRoot = mkOption {
        type = types.str;
        description = "Docker data root directory.";
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
      description = "Service metadata defined in hosts/home-stockholm/services.d";
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
                kubernetes = mkOption {
                  type = types.nullOr (types.submodule {
                    options = {
                      namespace = mkOption {
                        type = types.str;
                        description = "Kubernetes namespace containing the backed-up resources.";
                      };
                      deployments = mkOption {
                        type = types.listOf types.str;
                        default = [];
                        description = "Kubernetes deployments to scale down/up when the service is stopped for backup.";
                      };
                      pvcs = mkOption {
                        type = types.listOf types.str;
                        default = [];
                        description = "Kubernetes PersistentVolumeClaims to back up.";
                      };
                    };
                  });
                  default = null;
                  description = "Kubernetes backup targets for this service.";
                };
                preBackupCommands = mkOption {
                  type = types.listOf (types.listOf types.str);
                  default = [];
                  description = "Commands to run immediately before resolving and backing up targets.";
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

                      paths = mkOption {
                        type = types.listOf types.str;
                        default = backupCfg.paths;
                        description = "File paths to restore (defaults to backup.paths).";
                      };

                      kubernetes = mkOption {
                        type = types.nullOr (types.submodule {
                          options = {
                            namespace = mkOption {
                              type = types.str;
                              description = "Kubernetes namespace containing the restored resources.";
                            };
                            deployments = mkOption {
                              type = types.listOf types.str;
                              default = [];
                              description = "Kubernetes deployments to scale down/up during restore.";
                            };
                            pvcs = mkOption {
                              type = types.listOf types.str;
                              default = [];
                              description = "Kubernetes PersistentVolumeClaims to restore.";
                            };
                          };
                        });
                        default = backupCfg.kubernetes;
                        description = "Kubernetes restore targets (defaults to backup.kubernetes).";
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
    };
  };
}
