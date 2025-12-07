{ ... }:
{
  environment.variables.HOMEBREW_NO_ANALYTICS = "1";

  homebrew = {
    enable = true;

    # Uninstall packages not listed here
    onActivation = {
      autoUpdate = true;
      cleanup = "zap"; # Remove unlisted casks and formulae
      upgrade = true;
    };

    # CLI tools installed via Homebrew (when not available in nixpkgs)
    brews = [
      "gitui" # nixos version doesn't compile on macos
    ];

    # macOS Applications (GUI apps)
    casks = [
      "alacritty"
      "anki"
      "codex"
      "db-browser-for-sqlite"
      "discord"
      "easy-move+resize"
      "firefox"
      "font-hack-nerd-font"
      "ghostty"
      "iterm2"
      "karabiner-elements"
      "obsidian"
      "raycast"
      "spotify"
      "tailscale-app"
      "telegram-desktop"
      "ticktick"
      "tor-browser"
      "xld" # Audio converter
    ];

    masApps = {
    };
  };
}
