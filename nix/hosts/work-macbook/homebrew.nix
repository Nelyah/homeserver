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
      "easy-move+resize"
      "firefox"
      "font-hack-nerd-font"
      # "ghostty" # built from custom fork via activation script
      "karabiner-elements"
      "raycast"
      "tailscale-app"
      # TODO: Add work-specific apps here
    ];

    masApps = {
    };
  };
}
