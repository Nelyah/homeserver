{...}: {
  imports = [
    ./hardware-configuration.nix
    ./options.nix
    ./services.nix           # Must come after options.nix
    ./base.nix
    ./kubernetes.nix
    ./storage.nix
    ./networking.nix
    ./docker
    ./frp.nix
    ./vault-agent.nix
    ./vault-unseal.nix
    ./backup
    ./disk-health.nix
    ./geoip-updater.nix
  ];
}
