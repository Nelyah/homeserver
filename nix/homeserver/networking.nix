{ ... }:
{
  services.openssh = {
    enable = true;
    ports = [ 2541 ];
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
      X11Forwarding = false;
      AllowUsers = [ "chloe" ];
    };
  };

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [
      80
      443
      53
      2541
    ];
  };

  services.fail2ban = {
    enable = true;
    bantime = "1h";
    ignoreIP = [
      "127.0.0.1/8"
      "::1"
      "192.168.1.0/24"
      "100.64.0.0/10"
    ];
    jails.sshd.settings = {
      enabled = true;
      port = "2541";
      maxretry = 1;
      bantime = "-1";
      findtime = 1800;
    };
  };

  services.dnsmasq = {
    enable = true;
    settings = {
      interface = [ "tailscale0" ];
      no-resolv = true;
      "cache-size" = 10000;
      address = [ "/nelyah.eu/100.116.21.31" ];
    };
  };

  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  imports = [ ./tailscale-authkey.nix ];

  networking.hostName = "home-stockholm";
}
