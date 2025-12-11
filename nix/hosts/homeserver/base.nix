{
  pkgs,
  config,
  inputs,
  ...
}: {
  # Homeserver-specific nix settings (common settings in modules/common.nix)
  nix.gc = {
    automatic = true;
    dates = "weekly";
    options = "--delete-older-than 30d";
  };

  users.users.chloe = {
    isNormalUser = true;
    extraGroups = [
      "wheel"
      "docker"
      "data"
    ];
    shell = pkgs.zsh;
  };

  i18n = {
    defaultLocale = "en_GB.UTF-8";
    supportedLocales = ["en_GB.UTF-8/UTF-8"];
  };

  time.timeZone = "Europe/Stockholm";

  # Homeserver-specific packages (common packages are in modules/common.nix)
  environment.systemPackages =
    (with pkgs; [
      # System tools
      bash
      gcc
      gdb
      net-tools
      ethtool
      duf
      smartmontools
      davfs2

      # Backup & sync
      restic

      # Email
      isync
      msmtp
      neomutt
      notmuch

      # Media
      beets

      # Development
      python3Packages.pip
    ])
    ++ [inputs.codex-cli-nix.packages.${pkgs.system}.default];

  environment.variables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    CARGO_HOME = "$HOME/.cargo";
    RUSTUP_HOME = "$HOME/.rustup";
    GOPATH = "$HOME/.local/share/go";
  };

  environment.shellInit = ''
    git_repo_path=${config.homeserver.homeserverRoot}
    services_directory="${"$"}{git_repo_path}/services"
    export PATH="${"$"}{git_repo_path}/bin:${"$"}{PATH}"
    alias cdd="cd ${"$"}{git_repo_path}"
    alias cddd="cd ${"$"}{services_directory}"
    alias cdn="cd ${"$"}{services_directory}/nextcloud"
    alias cdw="cd ${"$"}{services_directory}/wordpress"
  '';

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

  system.stateVersion = "25.11";
}
