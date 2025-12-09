{
  pkgs,
  config,
  ...
}: {
  nix = {
    settings = {
      experimental-features = [
        "nix-command"
        "flakes"
      ];
      warn-dirty = false;
    };
    gc = {
      automatic = true;
      dates = "weekly";
      options = "--delete-older-than 30d";
    };
  };

  nixpkgs.config.allowUnfree = true;

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

  programs.zsh.enable = true;

  environment.systemPackages = with pkgs; [
    bat
    beets
    cacert
    cmake
    codex
    gcc
    gnumake
    alejandra
    cmake
    claude-code
    pkg-config
    nixd
    yadm
    curl
    davfs2
    duf
    ethtool
    flac
    bash
    delta
    gdb
    git
    gnupg
    htop
    imagemagick
    isync
    jq
    lnav
    msmtp
    nodejs
    ncdu
    neovim
    net-tools
    python3
    python3Packages.pip
    restic
    ripgrep
    rsync
    smartmontools
    tig
    tailscale
    tmux
    unzip
    wget
    yq
    zsh
    fzf
    universal-ctags
    go
    neomutt
    notmuch
  ] ++ (with pkgs.unstable; [
    claude-code
  ]);

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
