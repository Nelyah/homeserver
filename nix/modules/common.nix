{
  pkgs,
  lib,
  inputs,
  ...
}: {
  options.server.repoRoot = lib.mkOption {
    type = lib.types.str;
    default = "~/homeserver";
    description = "Root path of the homeserver repo on the host.";
  };

  config = {

  nixpkgs.overlays = [
    inputs.bive.overlays.default
    (_final: prev: {
      bive = prev.bive.overrideAttrs {doCheck = false;};
    })
  ];

  # Nix settings shared across all hosts
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
      options = "--delete-older-than 30d";
    } // (if pkgs.stdenv.isLinux then {
      dates = "Sun *-*-* 02:00:00";
    } else {
      interval = {
        Weekday = 0;
        Hour = 2;
        Minute = 0;
      };
    });
  };

  nixpkgs.config.allowUnfree = true;

  # Union of packages from darwin and homeserver that work on both platforms
  environment.systemPackages = with pkgs;
    [
      # Nix tools
      alejandra
      nixd
      nixfmt

      # Shell & terminal
      bat
      delta
      eza
      graphviz
      fd
      fzf
      dig
      btop
      htop
      btop
      jq
      lf
      ncdu
      ripgrep
      tmux
      tree
      yq
      zsh
      lefthook
      taplo # TOML formatter
      gh # github cli

      # Version control
      git
      tig
      yadm

      ollama

      # Editors
      neovim
      emacs

      # Build tools
      cmake
      ccache
      clang
      gcc
      gnumake
      pkg-config
      ninja
      pyright
      ruff
      docker
      devcontainer

      # Languages & runtimes
      go
      nodejs
      python3
      lua
      rustup
      cargo
      zig

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
      rclone
      unzip
      yt-dlp

      # Other utilities
      bive
      atuin
      ansible
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
    ]
    ++ (with pkgs.unstable; [
      claude-code
      cursor-cli
    ])
    ++ [
      pkgs.claude-agent-acp
      inputs.codex-cli-nix.packages.${pkgs.stdenv.hostPlatform.system}.default
      inputs.codex-acp-nix.packages.${pkgs.stdenv.hostPlatform.system}.default
    ];

  # Enable zsh on all hosts
  programs.zsh.enable = true;

  };
}
