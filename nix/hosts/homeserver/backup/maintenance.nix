{
  pkgs,
  lib,
  ...
}: let
  resticCmd = "${pkgs.restic}/bin/restic";
  resticEnv = env: "/var/lib/secrets/restic/${env}.env";

  mkMaint = {
    name,
    env, # "local" | "remote"
    description,
    calendar,
    script,
  }: {
    services.${name} = {
      inherit description script;
      serviceConfig = {
        Type = "oneshot";
        EnvironmentFile = resticEnv env;
        OnFailure = "pushover-notify@%n.service";
      };
    };
    timers.${name} = {
      description = "${description} timer";
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = calendar;
        Persistent = true;
      };
    };
  };

  maintUnits =
    lib.foldl' lib.recursiveUpdate {services = {}; timers = {};} [
      (mkMaint {
        name = "check-backup";
        env = "local";
        description = "Restic repository integrity check (local)";
        calendar = "*-*-02 02:00:00";
        script = "${resticCmd} check";
      })
      (mkMaint {
        name = "check-backup-remote";
        env = "remote";
        description = "Restic repository integrity check (remote)";
        calendar = "*-*-02 12:00:00";
        script = "${resticCmd} check";
      })
      (mkMaint {
        name = "check-backup-data";
        env = "local";
        description = "Restic partial data verification (local)";
        calendar = "*-*-15 02:00:00";
        script = ''
          SUBSET_FILE="/var/lib/restic/local-subset-counter"
          mkdir -p /var/lib/restic
          CURRENT=$(${pkgs.coreutils}/bin/cat "$SUBSET_FILE" 2>/dev/null || echo "1")
          echo "Checking subset $CURRENT/12 of local repository"
          ${resticCmd} check --read-data-subset="$CURRENT/12"
          NEXT=$(( (CURRENT % 12) + 1 ))
          echo "$NEXT" > "$SUBSET_FILE"
        '';
      })
      (mkMaint {
        name = "check-backup-data-remote";
        env = "remote";
        description = "Restic partial data verification (remote)";
        calendar = "*-*-15 12:00:00";
        script = ''
          SUBSET_FILE="/var/lib/restic/remote-subset-counter"
          mkdir -p /var/lib/restic
          CURRENT=$(${pkgs.coreutils}/bin/cat "$SUBSET_FILE" 2>/dev/null || echo "1")
          echo "Checking subset $CURRENT/12 of remote repository"
          ${resticCmd} check --read-data-subset="$CURRENT/12"
          NEXT=$(( (CURRENT % 12) + 1 ))
          echo "$NEXT" > "$SUBSET_FILE"
        '';
      })
    ];
in {
  systemd.services =
    maintUnits.services
    // {
      "pushover-notify@" = {
        description = "Send Pushover notification for %i";
        serviceConfig = {
          Type = "oneshot";
          EnvironmentFile = "/var/lib/secrets/pushover.env";
          Environment = "SERVICE=%i";
        };
        script = ''
          ${pkgs.curl}/bin/curl -s \
            -F "token=$PUSHOVER_TOKEN" \
            -F "user=$PUSHOVER_USER" \
            -F "title=Homeserver Alert: ''${SERVICE:-unknown} failed" \
            -F "message=Service ''${SERVICE:-unknown} has failed. Check logs with: journalctl -u ''${SERVICE:-unknown}" \
            -F "sound=pushover" \
            -F "priority=1" \
            https://api.pushover.net/1/messages.json
        '';
      };
    };

  systemd.timers = maintUnits.timers;

  systemd.tmpfiles.rules = [
    "d /var/lib/restic 0700 root root -"
  ];
}
