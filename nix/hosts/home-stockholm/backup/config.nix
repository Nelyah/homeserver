# Generates /etc/svc/services.json for the svc Python CLI tool
# This file serializes all service metadata from Nix to JSON
{
  pkgs,
  lib,
  config,
  ...
}: let
  services = config.homeserver.services;

  # Serialize retention policy to JSON-safe format
  serializePolicy = policy:
    if policy == null
    then null
    else {
      last = policy.last or null;
      hourly = policy.hourly or null;
      daily = policy.daily or null;
      weekly = policy.weekly or null;
      monthly = policy.monthly or null;
      yearly = policy.yearly or null;
    };

  # Serialize restore config
  serializeRestore = name: svc: let
    backup = svc.backup or {};
    restore = backup.restore or {};
    restic = restore.restic or {};
    kubernetes = restore.kubernetes or (backup.kubernetes or null);
  in {
    tag = restore.tag or name;
    paths = restore.paths or (backup.paths or []);
    kubernetes =
      if kubernetes == null
      then null
      else {
        namespace = kubernetes.namespace;
        deployments = kubernetes.deployments or [];
        pvcs = kubernetes.pvcs or [];
      };
    target = restic.target or "/";
  };

  # Serialize a single service to JSON-safe format
  serializeService = name: svc: let
    backup = svc.backup or {};
    backupEnabled = backup.enable or false;
    kubernetes = backup.kubernetes or null;
  in {
    inherit name;
    backup = {
      enable = backupEnabled;
      paths = backup.paths or [];
      kubernetes =
        if kubernetes == null
        then null
        else {
          namespace = kubernetes.namespace;
          deployments = kubernetes.deployments or [];
          pvcs = kubernetes.pvcs or [];
        };
      preBackupCommands = backup.preBackupCommands or [];
      tags = backup.tags or [name];
      exclude = backup.exclude or [];
      policy = serializePolicy (backup.policy or null);
    };
    restore = serializeRestore name svc;
  };

  # Build complete config structure
  configData = {
    paths = {
      secretsRoot = config.homeserver.paths.secretsRoot;
      backupMetadataRoot = "/var/lib/svc/backup-metadata";
    };
    services = lib.mapAttrs serializeService services;
  };

  configJson = pkgs.writeText "svc-services.json" (builtins.toJSON configData);
in {
  environment.etc."svc/services.json".source = configJson;
}
