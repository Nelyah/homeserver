# Generates /etc/svc/services.json for the svc Python CLI tool
# This file serializes all service metadata from Nix to JSON
{
  pkgs,
  lib,
  config,
  ...
}: let
  homeserverLib = import ../lib {inherit lib;};
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
  in {
    tag = restore.tag or name;
    volumes = restore.volumes or (backup.volumes or []);
    paths = restore.paths or (backup.paths or []);
    stopCompose =
      restore.stopCompose
      or (svc ? compose && svc.compose != null && (svc.compose.enable or false));
    composeUnit =
      if (restore.composeUnit or null) != null
      then restore.composeUnit
      else "docker-compose-${name}.service";
    target = restic.target or "/";
  };

  # Serialize a single service to JSON-safe format
  serializeService = name: svc: let
    backup = svc.backup or {};
    backupEnabled = backup.enable or false;
  in {
    inherit name;
    backup = {
      enable = backupEnabled;
      needsServiceStopped = backup.needsServiceStopped or false;
      volumes = backup.volumes or [];
      paths = backup.paths or [];
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
      deployRoot = config.homeserver.paths.deployRoot;
      dockerVolumesRoot = config.homeserver.paths.dockerVolumesRoot;
    };
    services = lib.mapAttrs serializeService services;
  };

  configJson = pkgs.writeText "svc-services.json" (builtins.toJSON configData);
in {
  environment.etc."svc/services.json".source = configJson;
}
