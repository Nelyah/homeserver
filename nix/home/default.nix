{
  pkgs,
  username,
  lib,
  config,
  ...
}: {
  home = {
    username = username;
    homeDirectory = "/Users/${username}";
    stateVersion = "24.05";

    sessionPath = [
      "$HOME/bin"
      "$CARGO_HOME/bin"
      "$GOPATH/bin"
    ];

    # User-specific packages
    packages = with pkgs; [
    ];

    # Environment variables
    sessionVariables = {
      EDITOR = "nvim";
      VISUAL = "nvim";
      CARGO_HOME = "$HOME/.cargo";
      RUSTUP_HOME = "$HOME/.rustup";
      GOPATH = "$HOME/.local/share/go";
    };
  };

  # Ensure screenshots directory exists for this user
  home.activation.createScreenshotsDir = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
    mkdir -p "${config.home.homeDirectory}/Pictures/screenshots"
  '';

  # Let Home Manager manage itself
  programs.home-manager.enable = true;
}
