{ config, pkgs, ... }:

{
  # GeoIP database storage directory
  systemd.tmpfiles.rules = [
    "d /var/lib/geoip 0755 root root -"
  ];

  # Weekly update service
  systemd.services.geoip-update = {
    description = "Update MaxMind GeoLite2 database";
    serviceConfig = {
      Type = "oneshot";
      ExecStart = pkgs.writeShellScript "geoip-update" ''
        set -euo pipefail
        ${pkgs.curl}/bin/curl -fsSL -o /var/lib/geoip/GeoLite2-Country.mmdb.tmp \
          "https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb"
        mv /var/lib/geoip/GeoLite2-Country.mmdb.tmp /var/lib/geoip/GeoLite2-Country.mmdb
      '';
    };
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
  };

  # Run weekly on Sunday at 3 AM
  systemd.timers.geoip-update = {
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnCalendar = "Sun *-*-* 03:00:00";
      Persistent = true; # Run immediately if missed
      RandomizedDelaySec = "1h";
    };
  };
}
