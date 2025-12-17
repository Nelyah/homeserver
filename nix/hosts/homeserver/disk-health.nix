# Disk health monitoring with smartctl
# Creates 3 timers:
# - disk-health-quick: Daily health check (milliseconds, just reads SMART status)
# - disk-health-short: Weekly short self-test (~2 min)
# - disk-health-long: Semi-annual long self-test (hours)
#
# Results are written to /var/lib/disk-health/status.json for svc doctor to read.
# JSON structure tracks each test type separately per drive:
# {
#   "lastUpdate": "timestamp",
#   "drives": [
#     {
#       "device": "/dev/sda",
#       "model": "...",
#       "serial": "...",
#       "quick": {"status": "healthy", "lastRun": "timestamp"},
#       "short": {"status": "healthy", "lastRun": "timestamp"},
#       "long": null
#     }
#   ]
# }
{
  pkgs,
  lib,
  ...
}: let
  stateDir = "/var/lib/disk-health";
  reportFile = "${stateDir}/status.json";
  smartctl = "${pkgs.smartmontools}/bin/smartctl";
  jq = "${pkgs.jq}/bin/jq";

  # Generic check script - takes check type as argument
  # Usage: check-disk-health [quick|short|long]
  checkScript = pkgs.writeShellScript "check-disk-health" ''
    set -euo pipefail

    CHECK_TYPE="''${1:-quick}"
    mkdir -p ${stateDir}

    TIMESTAMP=$(date -Iseconds)
    FAILED=false

    # Load existing report or create empty structure
    if [ -f "${reportFile}" ]; then
      EXISTING=$(cat "${reportFile}")
    else
      EXISTING='{"lastUpdate": null, "drives": []}'
    fi

    for drive in /dev/sd[a-z] /dev/nvme[0-9]n[0-9]; do
      [ -b "$drive" ] || continue

      case "$CHECK_TYPE" in
        quick)
          # Just health status (milliseconds)
          OUTPUT=$(${smartctl} -H "$drive" 2>&1 || true)
          if echo "$OUTPUT" | grep -q "PASSED"; then
            STATUS="healthy"
          else
            STATUS="failed"
            FAILED=true
          fi
          ;;
        short)
          # Start short self-test, then check result
          ${smartctl} -t short "$drive" >/dev/null 2>&1 || true
          sleep 120  # Wait for short test (~2 min)
          OUTPUT=$(${smartctl} -l selftest "$drive" 2>&1 || true)
          if echo "$OUTPUT" | grep -q "Completed without error"; then
            STATUS="healthy"
          else
            STATUS="degraded"
            FAILED=true
          fi
          ;;
        long)
          # Start long self-test (runs in background on drive)
          ${smartctl} -t long "$drive" >/dev/null 2>&1 || true
          # Don't wait - just trigger it, next quick check will see results
          STATUS="testing"
          ;;
        *)
          echo "Unknown check type: $CHECK_TYPE" >&2
          exit 1
          ;;
      esac

      # Get model/serial
      INFO=$(${smartctl} -i "$drive" 2>/dev/null || echo "")
      MODEL=$(echo "$INFO" | grep -i "Device Model\|Model Number" | head -1 | cut -d: -f2 | xargs || echo "unknown")
      SERIAL=$(echo "$INFO" | grep -i "Serial Number" | head -1 | cut -d: -f2 | xargs || echo "unknown")

      # Update the specific test type for this drive, preserving other test results
      TEST_RESULT=$(${jq} -n --arg status "$STATUS" --arg lastRun "$TIMESTAMP" \
        '{status: $status, lastRun: $lastRun}')

      EXISTING=$(echo "$EXISTING" | ${jq} \
        --arg dev "$drive" \
        --arg model "$MODEL" \
        --arg serial "$SERIAL" \
        --arg checkType "$CHECK_TYPE" \
        --argjson testResult "$TEST_RESULT" \
        --arg timestamp "$TIMESTAMP" \
        '
        .lastUpdate = $timestamp |
        if (.drives | map(.device) | index($dev)) then
          # Update existing drive entry
          .drives |= map(
            if .device == $dev then
              .model = $model |
              .serial = $serial |
              .[$checkType] = $testResult
            else . end
          )
        else
          # Add new drive entry
          .drives += [{
            device: $dev,
            model: $model,
            serial: $serial,
            quick: null,
            short: null,
            long: null,
            ($checkType): $testResult
          }]
        end
        ')
    done

    # Write updated report
    echo "$EXISTING" > ${reportFile}

    if [ "$FAILED" = "true" ]; then
      echo "SMART check ($CHECK_TYPE) failed for one or more drives" >&2
      exit 1
    fi

    echo "All drives healthy ($CHECK_TYPE check)"
  '';

  mkTimer = name: calendar: checkType: {
    services."disk-health-${name}" = {
      description = "Check disk SMART health (${name})";
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${checkScript} ${checkType}";
        OnFailure = "pushover-notify@%n.service";
      };
    };
    timers."disk-health-${name}" = {
      wantedBy = ["timers.target"];
      timerConfig = {
        OnCalendar = calendar;
        Persistent = true;
      };
    };
  };

  # Merge all timer configs
  timerConfigs = lib.foldl' lib.recursiveUpdate {} [
    (mkTimer "quick" "daily" "quick")
    (mkTimer "short" "weekly" "short")
    (mkTimer "long" "*-01,07-01" "long") # Jan 1 and Jul 1 (every 6 months)
  ];
in {
  systemd.services = timerConfigs.services;
  systemd.timers = timerConfigs.timers;

  systemd.tmpfiles.rules = [
    "d ${stateDir} 0755 root root -"
  ];
}
