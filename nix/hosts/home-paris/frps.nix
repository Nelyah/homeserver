{
  pkgs,
  lib,
  ...
}: {
  services.frp = {
    enable = true;
    role = "server";
    settings = {
      bindPort = 7000;
      transport.tls.force = true;
      allowPorts = [
        {single = 80;}
        {single = 443;}
      ];
      auth.method = "token";
      auth.tokenSource = {
        type = "file";
        file.path = "/var/lib/secrets/frp-token";
      };
    };
  };

  systemd.services.frp = {
    after = [
      "network-online.target"
      "tailscale-online.target"
    ];
    wants = [
      "network-online.target"
      "tailscale-online.target"
    ];
    unitConfig.StartLimitIntervalSec = 0;
    serviceConfig = {
      # Make sure we are running this as root and not $USER
      DynamicUser = lib.mkForce false;
      Restart = lib.mkForce "always";
      RestartSec = lib.mkForce "10s";
    };
  };

  systemd.tmpfiles.rules = [
    "d /var/lib/secrets 0700 root root -"
  ];
}
