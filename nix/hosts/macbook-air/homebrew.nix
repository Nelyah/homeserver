{...}: {
  environment.variables.HOMEBREW_NO_ANALYTICS = "1";

  homebrew = {
    enable = true;

    # Uninstall packages not listed here
    onActivation = {
      autoUpdate = true;
      cleanup = "zap"; # Remove unlisted casks and formulae
      upgrade = true;
    };

    # CLI tools installed via Homebrew
    brews = [
      "gitui" # nixos version doesn't compile on macos
    ];

    # macOS Applications (GUI apps)
    casks = [
      "anki"
      "rectangle-pro"
      "calibre"
      "db-browser-for-sqlite"
      "discord"
      "easy-move+resize"
      "firefox"
      "font-hack-nerd-font"
      "iterm2"
      "karabiner-elements"
      "obsidian"
      "raycast"
      "spotify"
      "qbittorrent"
      "tailscale-app"
      "telegram-desktop"
      "ticktick"
      "tor-browser"
      "xld" # Audio converter
    ];

    # MacOS App store apps
    # Add the app id, in the format as below:
    # "Xcode" = 497799835;
    masApps = {
    };
  };
}
