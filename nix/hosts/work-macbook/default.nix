{username, ...}: {
  imports = [
    ./homebrew.nix
  ];

  system.stateVersion = 5;

  system.defaults.dock.persistent-apps = [
    # TODO: Add work dock apps here
    {app = "/Applications/Firefox.app";}
    {app = "/Applications/Ghostty.app";}
  ];

  home-manager.users.${username} = import ../../home;
}
