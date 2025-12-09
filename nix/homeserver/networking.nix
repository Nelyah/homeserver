{
  pkgs,
  lib,
  ...
}: let
  public_dns = ["1.1.1.1" "1.0.0.1" "8.8.8.8"];
in {
  networking.hostName = "home-stockholm";

  services.openssh = {
    enable = true;
    ports = [22];
    settings = {
      PasswordAuthentication = false;
      PermitRootLogin = "no";
      X11Forwarding = false;
      AllowUsers = ["chloe"];
    };
  };

  networking.firewall = {
    enable = true;
    allowedTCPPorts = [
      80
      443
      53
      22
    ];
    allowedUDPPorts = [
      53
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

  services.tailscale = {
    enable = true;
    useRoutingFeatures = "client";
  };

  systemd.services.tailscaled = {
    after = ["network-online.target"];
    wants = ["network-online.target"];
  };

  imports = [./tailscale-authkey.nix];

  # Because we manage network with systemd, disable the legacy dhcpd client
  # and rely on systemd-netowrkd instead
  networking.dhcpcd.enable = false;
  networking.useDHCP = false;
  systemd.network.enable = true;

  systemd.network.networks."enp1s0" = {
    matchConfig.Name = "enp1s0";
    networkConfig = {
      DHCP = "yes";
      DNS = ["127.0.0.1"];
    };
    dhcpConfig.UseDNS = false;
  };

  networking.nameservers = ["127.0.0.1"];

  # Resolved is highjacking all DNS queries by plugging into /etc/resolv.conf which refers to 127.0.0.53 (<-- resolved)
  # Its goal is to figure out to which DNS to send the query
  #
  # resolved gets the DNS it should hit by the DNS configured for the interfaces.
  # In our case it's networkd, but it could be NetworkManager or some other
  # For this setup, it will wire everything to a local DNS, which we run with dnsmasq
  #
  # The tailscale0 interface is managed directly by tailscale, and it will redirect queries there to its MagicDNS
  # The Magic DNS from tailscale has the splitDNS setup for *.nelyah.eu, which says 'go check this server's DNS server'
  # So anything arriving to the tailscale0 interface ends up pinging dnsmasq through tailscale.
  # In dnsmasq, we do a couple of things:
  # - if the DNS query is a nelyah.eu, then we return this server's tailscale IP
  #     This will make sure that services connecting to *.nelyah.eu and using this DNS will connect on the tailscale0 interface
  #     This then lets me do filtering with the reverse proxy and so on
  # - else, we are redirectory to the list of public DNS
  services.resolved = {
    enable = true;
    dnssec = "false";
    domains = ["~."];
    fallbackDns = public_dns;
  };

  services.dnsmasq = {
    enable = true;
    resolveLocalQueries = false;
    settings = {
      interface = ["lo" "tailscale0"];
      bind-dynamic = true;
      log-queries = true;
      no-resolv = true;
      "cache-size" = 10000;
      server = public_dns;
      "conf-dir" = "/run/dnsmasq.d";
    };
  };

  # Generate a per-boot dnsmasq snippet with the current Tailscale IP.
  # TODO: At some point I will want to include IPv6, but I don't think I have it handled with Caddy yet
  systemd.services.dnsmasq = {
    after = ["tailscaled.service"];
    wants = ["tailscaled.service"];
    path = [
      pkgs.dnsmasq
      pkgs.coreutils
    ];
    serviceConfig.ExecStartPre = lib.mkBefore [
      (pkgs.writeShellScript "dnsmasq-generate-tailscale-conf" ''
                set -euo pipefail
                ts_ip="$(${pkgs.tailscale}/bin/tailscale ip -4 | head -n1)"
                if [[ -z "$ts_ip" ]]; then
                  echo "Failed to detect Tailscale IPv4 address" >&2
                  exit 1
                fi
                ts_ip_6="$(${pkgs.tailscale}/bin/tailscale ip -6 | head -n1)"
                if [[ -z "$ts_ip_6" ]]; then
                  echo "Failed to detect Tailscale IPv6 address" >&2
                  exit 1
                fi
                install -d -m 0755 /run/dnsmasq.d
                cat > /run/dnsmasq.d/tailscale.conf <<EOF
        address=/nelyah.eu/$ts_ip
        EOF
      '')
    ];
  };
}
