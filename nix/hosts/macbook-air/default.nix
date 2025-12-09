{
  pkgs,
  username,
  hostname,
  ...
}: {
  imports = [
    ./homebrew.nix
  ];

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
      interval = {
        Weekday = 0;
        Hour = 2;
        Minute = 0;
      };
      options = "--delete-older-than 30d";
    };
  };

  nixpkgs.config.allowUnfree = true;

  environment.systemPackages = with pkgs; [
    alejandra # formatter for nix files
    atuin
    bat
    cmake
    coreutils
    curl
    delta
    exiftool
    eza
    fd
    ffmpeg
    flac
    fzf
    gettext
    git
    gnupg
    go
    htop
    hugo
    imagemagick
    jq
    lf
    libiconv
    libintl
    lua
    ncdu
    neovim
    ninja
    nixd
    nixfmt-rfc-style
    nmap
    nodejs
    pkg-config
    pre-commit
    ripgrep
    rsync
    rustup
    tig
    tmux
    tree
    tree-sitter
    uv
    vim
    wget
    yadm
    yarn
    yq
    yt-dlp
  ];

  # Enable Touch ID for sudo
  security.pam.services.sudo_local.touchIdAuth = true;

  system = {
    defaults = {
      NSGlobalDomain = {
        # Keyboard settings
        ApplePressAndHoldEnabled = false;

        # Finder settings
        AppleShowAllExtensions = true;
        AppleShowAllFiles = true;

        # Disable automatic text corrections
        NSAutomaticCapitalizationEnabled = false;
        NSAutomaticDashSubstitutionEnabled = false;
        NSAutomaticPeriodSubstitutionEnabled = false;
        NSAutomaticSpellingCorrectionEnabled = false;
        AppleInterfaceStyleSwitchesAutomatically = true;

        AppleMeasurementUnits = "Centimeters";
        AppleMetricUnits = 1;
        AppleShowScrollBars = "Automatic";
        AppleTemperatureUnit = "Celsius";
      };

      dock = {
        autohide = true;
        autohide-delay = 0.0;
        autohide-time-modifier = 0.4;
        orientation = "bottom";
        show-recents = false;

        # Disable hot corners
        wvous-bl-corner = 1;
        # wvous-br-corner = 1;
        wvous-tl-corner = 1;
        wvous-tr-corner = 1;
        persistent-apps = [
          {
            app = "/Applications/Firefox.app";
          }
          {
            app = "/System/Applications/Mail.app";
          }
          {
            app = "/Applications/iTerm.app";
          }
          {
            app = "/Applications/Obsidian.app";
          }
          {
            app = "/Applications/Anki.app";
          }
          {
            app = "/System/Applications/Calendar.app";
          }
          {
            app = "/Applications/Signal.app";
          }
        ];
      };

      finder = {
        AppleShowAllExtensions = true;
        AppleShowAllFiles = true;
        FXEnableExtensionChangeWarning = false;
        FXPreferredViewStyle = "Nlsv"; # List view
        FXDefaultSearchScope = "SCcf"; # current folder
        ShowPathbar = true;
        ShowStatusBar = true;

        # Remove trash after 30 days
        FXRemoveOldTrashItems = true;

        _FXShowPosixPathInTitle = true;
        _FXSortFoldersFirst = true;
      };

      trackpad = {
        Clicking = true;
        TrackpadRightClick = true;
      };
      iCal = {
        CalendarSidebarShown = true;
        "first day of week" = "Monday";
      };

      menuExtraClock = {
        FlashDateSeparators = false;
        IsAnalog = false;
        Show24Hour = true;
      };

      screensaver.askForPasswordDelay = 600; # seconds

      screencapture.location = "/Users/${username}/Pictures/screenshots/";

      controlcenter.BatteryShowPercentage = true;
    };

    keyboard = {
      enableKeyMapping = true;
      remapCapsLockToControl = true;
    };

    # Used for backwards compatibility
    stateVersion = 5;
  };

  environment.extraOutputsToInstall = ["dev"];
  environment.pathsToLink = [
    "/include"
    "/lib"
  ];
  environment.variables = {
    PKG_CONFIG_PATH = "/run/current-system/sw/lib/pkgconfig";

    # Tell GCC/Clang where to find headers
    CPATH = "/run/current-system/sw/include";

    # Tell the linker where to find libraries
    LIBRARY_PATH = "/run/current-system/sw/lib";
    CMAKE_PREFIX_PATH = "/run/current-system/sw";
  };

  # Create /etc/zshrc that loads the nix-darwin environment
  programs.zsh.enable = true;

  # Set the primary user for user-level defaults/homebrew actions
  system.primaryUser = username;
  users.users.${username} = {
    shell = "/bin/zsh";
    name = username;
    home = "/Users/${username}";
  };

  networking.hostName = hostname;
}
