{pkgs, ...}: {
  imports = [
    ./hardware-configuration.nix
    ./frps.nix
  ];

  networking.hostName = "home-paris";

  users.users.chloe = {
    isNormalUser = true;
    extraGroups = ["wheel"];
    shell = pkgs.zsh;
  };

  users.users.root.shell = pkgs.zsh;

  time.timeZone = "Europe/Paris";

  networking.firewall.allowedTCPPorts = [22 80 443 7000];

  system.stateVersion = "25.11";
}
