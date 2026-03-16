{
  pkgs,
  username,
  ...
}: {
  imports = [
    ./homebrew.nix
  ];

  system.stateVersion = 5;

  system.defaults.dock.persistent-apps = [
    # TODO: Add work dock apps here
    {app = "/Applications/Firefox.app";}
    {app = "/Applications/Ghostty.app";}
    {app = "/Applications/Slack.app";}
    {app = "/Applications/Obsidian.app";}
    {app = "/Applications/Spotify.app";}
    {app = "/Applications/Claude.app";}
  ];
  environment.systemPackages = with pkgs; [
    mosh
    oci-cli
    gemini-cli
  ];

  home-manager.users.${username} = import ../../home;
}
