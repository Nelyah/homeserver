{
  pkgs,
  config,
  lib,
  ...
}:
let
  authKeyPath = "/run/secrets/tailscale-auth-key";
  ensureScript = pkgs.writeShellScript "tailscale-ensure-auth.sh" ''
    set -euo pipefail

    SYSTEMCTL="${pkgs.systemd}/bin/systemctl"
    TAILSCALE="${pkgs.tailscale}/bin/tailscale"
    JQ="${pkgs.jq}/bin/jq"
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

    while true; do
      case "$state" in
        "Running")
          exit 0
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
            exit 0
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
  '';
in
{
  # Run during activation (part of rebuild); fail rebuild on error.
  system.activationScripts.tailscaleEnsureAuth = ''
    ${ensureScript}
  '';

  # Keep permissions tight if the key exists.
  systemd.tmpfiles.rules = [
    "z ${authKeyPath} 0400 root root -"
  ];
}
