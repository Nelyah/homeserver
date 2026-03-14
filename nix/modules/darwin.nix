{
  pkgs,
  username,
  hostname,
  ...
}: {
  environment.systemPackages = with pkgs; [
    # character encoding conversion library
    # Linux has it by default, but not macos
    libiconv
    # Used for i18n localisation
    # Linux has it with gettext, but not macos
    libintl
  ];

  # Build custom Ghostty fork and install to /Applications
  system.activationScripts.postActivation.text = ''
    echo "Building Ghostty from custom fork..."
    GHOSTTY_SRC="/Users/${username}/builds/ghostty"
    if [ -d "$GHOSTTY_SRC" ]; then
      sudo -u ${username} HOME="/Users/${username}" /nix/var/nix/profiles/default/bin/nix develop "$GHOSTTY_SRC" --command bash -c "cd $GHOSTTY_SRC && zig build -Doptimize=ReleaseFast -Demit-macos-app && cd macos && ./build.nu --configuration Release" 2>&1 || { echo "Ghostty build failed"; exit 1; }
      rm -rf /Applications/Ghostty.app
      cp -R "$GHOSTTY_SRC/zig-out/Ghostty.app" /Applications/Ghostty.app
      # Force ad-hoc codesign so macOS accepts the binary
      /usr/bin/codesign --force --deep --sign - /Applications/Ghostty.app
      echo "Ghostty installed and signed."
    else
      echo "WARNING: Ghostty source not found at $GHOSTTY_SRC"
    fi
  '';

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
        AppleInterfaceStyle = "Dark";
        AppleInterfaceStyleSwitchesAutomatically = false;

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
