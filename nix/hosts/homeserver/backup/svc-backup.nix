# Run scheduled backups via the `svc` CLI (replaces legacy backup/restore scripts)
{
  pkgs,
  lib,
  config,
  ...
}: let
  homeserverLib = import ../lib {inherit lib;};

  services = config.homeserver.services;
  selected = homeserverLib.docker.filterEnabledBackup services;

  secretsRoot = config.homeserver.paths.secretsRoot;
  resticEnv = env: "${secretsRoot}/restic/${env}.env";

  svcPackage = import ./svc {inherit pkgs;};
  svcBin = "${svcPackage}/bin/svc";
in {
  homeserver.vault.secrets = {
    restic-local = {
      template = ''
        {{ with secret "homeserver_secrets/data/restic" -}}
        RESTIC_PASSWORD={{ .Data.data.LOCAL_PASSWD }}
        RESTIC_REPOSITORY=${config.homeserver.backupDrive}/backups
        {{ end -}}
      '';
      destination = "restic/local.env";
    };
    restic-remote = {
      template = ''
        {{ with secret "homeserver_secrets/data/restic" -}}
        RESTIC_PASSWORD={{ .Data.data.REMOTE_PASSWD }}
        RESTIC_REPOSITORY={{ .Data.data.REMOTE_ADDR }}:/home/chloe/USB/backups
        {{ end -}}
      '';
      destination = "restic/remote.env";
    };
  };

  assertions =
    lib.mapAttrsToList (name: svc: {
      assertion = (svc.backup.volumes or []) != [] || (svc.backup.paths or []) != [];
      message = "Service '${name}' has backup.enable = true but backup.volumes and backup.paths are both empty.";
    })
    selected;

  systemd.services = {
    backup = {
      description = "Restic backup (local)";
      after = ["network-online.target" "vault-agent.service"];
      wants = ["network-online.target" "vault-agent.service"];
      requires = ["vault-agent.service"];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStartSec = "12h";
        EnvironmentFile = resticEnv "local";
      };
      script = "${svcBin} backup local all";
    };

    backup-remote = {
      description = "Restic backup (remote)";
      after = ["network-online.target" "vault-agent.service"];
      wants = ["network-online.target" "vault-agent.service"];
      requires = ["vault-agent.service"];
      serviceConfig = {
        Type = "oneshot";
        TimeoutStartSec = "12h";
        EnvironmentFile = resticEnv "remote";
      };
      script = "${svcBin} backup remote all";
    };
  };

  systemd.timers = {
    backup = {
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "05:00";
      };
    };

    backup-remote = {
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = "Mon 05:00";
      };
    };
  };
}

