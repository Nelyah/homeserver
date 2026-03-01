{
  pkgs,
  lib,
  ...
}: {
  # Nix settings shared across all hosts
  nix = {
    settings = {
      experimental-features = [
        "nix-command"
        "flakes"
      ];
      warn-dirty = false;
    };
  };

  nixpkgs.config.allowUnfree = true;

  # Union of packages from darwin and homeserver that work on both platforms
  environment.systemPackages = with pkgs; [
    # Nix tools
    alejandra
    nixd
    nixfmt-rfc-style

    # Shell & terminal
    bat
    delta
    eza
    fd
    fzf
    dig
    htop
    jq
    lf
    ncdu
    ripgrep
    tmux
    tree
    yq
    zsh

    # Version control
    git
    pre-commit
    tig
    yadm

    # Editors
    neovim
    vim

    # Build tools
    cmake
    clang
    gcc
    gnumake
    pkg-config
    ninja
    ruff

    # Languages & runtimes
    go
    nodejs
    python3
    lua

    # Network & web
    curl
    nmap
    wget

    # Media & files
    exiftool
    ffmpeg
    flac
    imagemagick
    rsync
    unzip
    yt-dlp

    # Other utilities
    atuin
    cacert
    coreutils
    gettext
    gnupg
    hugo
    lnav
    tree-sitter
    universal-ctags
    uv
    yarn
  ] ++ (with pkgs.unstable; [
    codex
    claude-code
  ]);

  # Enable zsh on all hosts
  programs.zsh.enable = true;
}
