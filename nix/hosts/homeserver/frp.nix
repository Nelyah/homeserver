{lib, ...}: {
  services.frp = {
    enable = true;
    role = "client";
    settings = {

      auth.method = "token";
      auth.tokenSource.type = "file";
      # Systemd credentials pushes the file at that location when the service starts
      auth.tokenSource.file.path = "/run/credentials/frp.service/frp-token";
      transport.tls.enable = true;

      serverAddr = "100.75.232.42"; # tailscale IP
      serverPort = 7000;

      proxies = [
        {
          name = "forward-https";
          type = "tcp";
          localIP = "127.0.0.1";
          localPort = 443;
          remotePort = 443;
          transport.proxyProtocolVersion = "v2";
        }
        {
          name = "forward-http";
          type = "tcp";
          localIP = "127.0.0.1";
          localPort = 80;
          remotePort = 80;
          transport.proxyProtocolVersion = "v2";
        }
      ];
    };
  };

  # Make frp wait for tailscale to be online and restart if it goes offline.
  systemd.services.frp = {
    # Only start when the token exists and avoid manual starts.
    unitConfig = {
      ConditionPathExists = "/var/lib/secrets/frp-token";
      StartLimitIntervalSec = 0; # retry indefinitely
    };
    after = [
      "network-online.target"
      "tailscale-online.target"
    ];
    wants = [
      "network-online.target"
      "tailscale-online.target"
    ];
    bindsTo = ["tailscale-online.target"];
    serviceConfig = {
      Restart = lib.mkForce "always";
      RestartSec = lib.mkForce "10s";
      DynamicUser = lib.mkForce true;
      LoadCredential = ["frp-token:/var/lib/secrets/frp-token"];
    };
  };

  # Trigger frp to start as soon as the token is rendered.
  systemd.paths."frp-token-exists" = {
    description = "Start frp when token is available";
    wantedBy = ["multi-user.target"];
    pathConfig = {
      PathExists = "/var/lib/secrets/frp-token";
      Unit = "frp.service";
    };
  };
}
