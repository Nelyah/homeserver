{pkgs, ...}: {
  # Shared NixOS server config (boot, users, locale, security, auto-updates)

  boot.loader.systemd-boot.enable = true;
  boot.loader.efi.canTouchEfiVariables = true;

  i18n = {
    defaultLocale = "en_GB.UTF-8";
    supportedLocales = ["en_GB.UTF-8/UTF-8"];
  };

  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  # SSH hardening
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

  networking.firewall.enable = true;

  # fail2ban: 1 retry = permanent ban for SSH
  services.fail2ban = {
    enable = true;
    bantime = "1h";
    ignoreIP = [
      "127.0.0.1/8"
      "::1"
      "100.64.0.0/10"
    ];
    jails.sshd.settings = {
      enabled = true;
      port = "22";
      maxretry = 1;
      bantime = "-1";
      findtime = 1800;
    };
  };

  # Security-only auto-updates
  system.autoUpgrade = {
    enable = true;
    dates = "03:30";
    flags = [
      "--upgrade"
      "--option"
      "upgrade-with-unsafe-packages"
      "false"
    ];
    allowReboot = true;
  };
}
