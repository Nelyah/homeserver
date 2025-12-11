{
  pkgs,
  lib,
  config,
  ...
}: let
  secretsRoot = "/var/lib/secrets";
  servicesDef = (import ../services.nix {inherit lib config pkgs;}).attrset;
  dockerRoot = "${config.homeserver.mainDrive}/docker-data";
  resticCmd = "${pkgs.restic}/bin/restic";
  resticEnv = env: "${secretsRoot}/restic/${env}.env";

  selected =
    lib.filterAttrs (
      _: service: (service.backup or null) != null && (service.backup.enable or false)
    )
    servicesDef;

  mkBackupScript = name: spec: let
    volArgs = map (v: "${dockerRoot}/volumes/${v}/") (spec.backup.volumes or []);
    pathArgs = spec.backup.paths or [];
    backupArgsStr = lib.concatStringsSep " " (volArgs ++ pathArgs);
    tags = spec.backup.tags or [name];
    tagFlags = lib.concatStringsSep " " (map (t: "--tag ${t}") tags);
    excludeFlags = lib.concatStringsSep " " (map (p: "--exclude '${p}'") (spec.backup.exclude or []));
    forget =
      spec.backup.policy or {
        daily = 10;
        weekly = 4;
        monthly = 4;
      };
    pre = spec.backup.pre or "";
    post = spec.backup.post or "";

    forgetCmd =
      if forget == null
      then ""
      else
        "${resticCmd} forget "
        + (lib.concatStringsSep " " (
          lib.filter (s: s != "") [
            (lib.optionalString ((forget.last or null) != null) "--keep-last ${toString (forget.last or 0)}")
            (lib.optionalString ((forget.hourly or null) != null) "--keep-hourly ${toString (forget.hourly or 0)}")
            (lib.optionalString ((forget.daily or null) != null) "--keep-daily ${toString (forget.daily or 0)}")
            (lib.optionalString (
              (forget.weekly or null) != null
            ) "--keep-weekly ${toString (forget.weekly or 0)}")
            (lib.optionalString (
              (forget.monthly or null) != null
            ) "--keep-monthly ${toString (forget.monthly or 0)}")
            (lib.optionalString (
              (forget.yearly or null) != null
            ) "--keep-yearly ${toString (forget.yearly or 0)}")
            "--prune"
          ]
        ))
        + " "
        + tagFlags;

    envPath = "${config.homeserver.homeserverRoot}/services/${name}/.env";
    binName = "backup-${name}";
  in
    pkgs.writeShellScriptBin binName ''
      #!${pkgs.bash}/bin/bash
      set -euo pipefail
      local_env="${resticEnv "local"}"
      remote_env="${resticEnv "remote"}"

      TARGET_ENV=${"$"}{1:?expected env choice: local|remote}
      shift || true

      case "$TARGET_ENV" in
        local) REPO_ENV="$local_env" ;;
        remote) REPO_ENV="$remote_env" ;;
        *) echo "unknown env: $TARGET_ENV (expected local|remote)" >&2; exit 1 ;;
      esac

      if [[ ! -f "$REPO_ENV" ]]; then
        echo "missing restic env $REPO_ENV" >&2
        exit 1
      fi
      source "$REPO_ENV"

      if [[ -f "${envPath}" ]]; then
        set -a
        source "${envPath}"
        set +a
      fi

      status=0
      # Deliberately capture errors instead of letting `set -e` bail out:
      # we want to run forget only on success and still execute post hooks before returning.
      ${pre}
      ${resticCmd} backup ${backupArgsStr} ${excludeFlags} ${tagFlags} || status=$?
      if [[ $status -eq 0 && -n "${forgetCmd}" ]]; then
        ${forgetCmd} || status=$?
      fi
      ${post}
      exit $status
    '';

  backupScripts = lib.mapAttrs (name: service: mkBackupScript name service) selected;
  backupScriptPaths =
    lib.mapAttrs' (name: drv: {
      inherit name;
      value = "${drv}/bin/backup-${name}";
    })
    backupScripts;
  selectedNames = lib.attrNames selected;

  backupRunner = pkgs.writeShellScriptBin "backup" ''
    #!${pkgs.bash}/bin/bash
    set -euo pipefail

    TARGET_ENV=${"$"}{1:?expected env choice: local|remote}
    TARGET_SVC=${"$"}{2:-all}
    shift 2 || true

    if [[ "$TARGET_SVC" == "all" ]]; then
      set -- ${lib.concatStringsSep " " selectedNames}
    else
      set -- "$TARGET_SVC"
    fi

    for service in "$@"; do
      case "$service" in
      ${lib.concatStringsSep "\n" (
      lib.mapAttrsToList (name: path: "  ${name}) cmd=\"${path}\" ;;") backupScriptPaths
    )}
        *) echo "unknown backup target: $service" >&2; exit 1 ;;
      esac
      "$cmd" "$TARGET_ENV"
    done
  '';
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

  environment.systemPackages = (lib.attrValues backupScripts) ++ [backupRunner];

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
      script = "${backupRunner}/bin/backup local";
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
      script = "${backupRunner}/bin/backup remote";
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
