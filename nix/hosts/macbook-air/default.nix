{username, pkgs, ...}: {
  imports = [
    ./homebrew.nix
  ];

  system.stateVersion = 5;

  system.defaults.dock.persistent-apps = [
    {app = "/Applications/Firefox.app";}
    {app = "/System/Applications/Mail.app";}
    {app = "/Applications/Ghostty.app";}
    {app = "/Applications/Obsidian.app";}
    {app = "/Applications/Anki.app";}
    {app = "/System/Applications/Calendar.app";}
    {app = "/Applications/Signal.app";}
  ];

  home-manager.users.${username} = import ../../home;

  environment.systemPackages = with pkgs;
    [
      whisky
    ];
}
