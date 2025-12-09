{
  pkgs,
  config,
  lib,
  ...
}: let
  # NixOS-specific: auth key path and monitoring script
  authKeyPath = "/run/secrets/tailscale-auth-key";
  monitorScript = pkgs.writeShellScript "tailscale-online.sh" ''
    set -euo pipefail

    SYSTEMCTL="${pkgs.systemd}/bin/systemctl"
    TAILSCALE="${pkgs.tailscale}/bin/tailscale"
    JQ="${pkgs.jq}/bin/jq"
    NOTIFY="${pkgs.systemd}/bin/systemd-notify"
    YELLOW="\033[33m"
    RED="\033[31m"
    GREEN="\033[32m"
    RESET="\033[0m"

    fetch_state() {
      status_json="$($TAILSCALE status --json 2>/dev/null || true)"
      state="$(printf '%s' "$status_json" | $JQ -r '.BackendState // "unknown"')"
    }

    wait_for_change() {
      target="$1"
      timeout="$2"
      message="$3"
      printf "%b%s%b\n" "$YELLOW" "$message" "$RESET"
      for ((i = 0; i < timeout; i++)); do
        fetch_state
        if [[ "$state" != "$target" && "$state" != "unknown" ]]; then
          return 0
        fi
        sleep 1
      done
      return 1
    }

    # Ensure tailscaled is active; start it if needed.
    ts_state="$($SYSTEMCTL is-active tailscaled.service || true)"
    if [[ "$ts_state" != "active" ]]; then
      $SYSTEMCTL start tailscaled.service || true
      sleep 1
      ts_state="$($SYSTEMCTL is-active tailscaled.service || true)"
      if [[ "$ts_state" != "active" ]]; then
        printf "%b%s%b\n" "$RED" "tailscaled.service is not active (state: $ts_state)" "$RESET" >&2
        exit 1
      fi
    fi

    fetch_state

    # Authentication loop - get tailscale to Running state
    while true; do
      case "$state" in
        "Running")
          break
          ;;

        "NoState")
          if wait_for_change "NoState" 15 "tailscale backend not initialized yet; waiting..."; then
            continue
          else
            printf "%b%s%b\n" "$RED" "tailscale stuck in NoState after waiting" "$RESET" >&2
            exit 1
          fi
          ;;

        "Starting")
          if wait_for_change "Starting" 60 "tailscale starting..."; then
            continue
          else
            printf "%b%s%b\n" "$RED" "tailscale stuck in Starting state after 60s" "$RESET" >&2
            exit 1
          fi
          ;;

        "Stopped")
          printf "%b%s%b\n" "$YELLOW" "tailscale backend stopped; attempting to bring it up" "$RESET"
          $TAILSCALE up || true
          if wait_for_change "Stopped" 60 "waiting for tailscale to leave Stopped state..."; then
            continue
          else
            printf "%b%s%b\n" "$RED" "tailscale stayed Stopped after restart attempt" "$RESET" >&2
            exit 1
          fi
          ;;

        "NeedsLogin")
          if [[ ! -f "${authKeyPath}" ]]; then
            printf "%b%s%b\n" "$RED" "tailscale needs login and ${authKeyPath} is missing" "$RESET" >&2
            exit 1
          fi
          key="$(${pkgs.coreutils}/bin/cat "${authKeyPath}")"
          if [[ -z "$key" ]]; then
            printf "%b%s%b\n" "$RED" "tailscale auth key file is empty" "$RESET" >&2
            exit 1
          fi
          printf "%b%s%b\n" "$YELLOW" "tailscale needs login; using auth key" "$RESET"
          $TAILSCALE up --authkey "$key"
          fetch_state
          if [[ "$state" == "Running" ]]; then
            printf "%b%s%b\n" "$GREEN" "tailscale authenticated successfully via auth key" "$RESET"
            break
          fi
          continue
          ;;

        "NeedsMachineAuth")
          if wait_for_change "NeedsMachineAuth" 60 "tailscale needs admin approval; waiting up to 60s..."; then
            continue
          else
            printf "%b%s%b\n" "$RED" "tailscale still needs admin approval after 60s" "$RESET" >&2
            exit 1
          fi
          ;;

        *)
          printf "%b%s%b\n" "$RED" "tailscale in unexpected state: $state" "$RESET" >&2
          exit 1
          ;;
      esac
    done

    # Verify we have an IP address
    ts_ip="$($TAILSCALE ip -4 2>/dev/null | head -n1 || true)"
    if [[ -z "$ts_ip" ]]; then
      printf "%b%s%b\n" "$RED" "tailscale is Running but has no IPv4 address" "$RESET" >&2
      exit 1
    fi

    # Signal systemd that we're ready
    printf "%b%s%b\n" "$GREEN" "tailscale online with IP: $ts_ip" "$RESET"
    $NOTIFY --ready --status="Tailscale online: $ts_ip"

    # Monitoring loop - check connectivity every 30 seconds
    while true; do
      sleep 30

      fetch_state
      if [[ "$state" != "Running" ]]; then
        printf "%b%s%b\n" "$RED" "tailscale went offline (state: $state)" "$RESET" >&2
        exit 1
      fi

      ts_ip="$($TAILSCALE ip -4 2>/dev/null | head -n1 || true)"
      if [[ -z "$ts_ip" ]]; then
        printf "%b%s%b\n" "$RED" "tailscale lost IP address" "$RESET" >&2
        exit 1
      fi

      $NOTIFY --status="Tailscale online: $ts_ip"
    done
  '';
in {
  config = lib.mkMerge [
    # Enable tailscale on all platforms
    {
      services.tailscale.enable = true;
    }

    # NixOS-only: tailscale-online target and monitoring service
    (lib.mkIf pkgs.stdenv.isLinux {
      # Target that represents "tailscale is online and authenticated"
      # bindsTo ensures the target stops when the service stops
      systemd.targets.tailscale-online = {
      description = "Tailscale is online and authenticated";
      wants = ["network-online.target" "tailscale-online.service"];
      after = ["network-online.target" "tailscale-online.service"];
      bindsTo = ["tailscale-online.service"];
    };

    # Service that waits for tailscale to be online, then monitors connectivity
    systemd.services.tailscale-online = {
      description = "Wait for and monitor Tailscale connectivity";
      after = ["network-online.target" "tailscaled.service"];
      wants = ["network-online.target" "tailscaled.service" "tailscale-online.target"];
      before = ["tailscale-online.target"];
      wantedBy = ["multi-user.target"];
      # Disable start-rate limiting so it keeps retrying even after repeated failures
      startLimitIntervalSec = 0;
      startLimitBurst = 0;

      serviceConfig = {
        Type = "notify";
        NotifyAccess = "main";
        ExecStart = monitorScript;
        Restart = "always";
        RestartSec = "10s";
      };
    };

    # Ensure tailscaled waits for network
    systemd.services.tailscaled = {
      after = ["network-online.target"];
      wants = ["network-online.target"];
    };

      # Keep permissions tight if the key exists.
      systemd.tmpfiles.rules = [
        "z ${authKeyPath} 0400 root root -"
      ];
    })
  ];
}
