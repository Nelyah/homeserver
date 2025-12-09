{...}: {
  imports = [
    ./boot.nix
    ./hardware-configuration.nix
    ./options.nix
    ./base.nix
    ./storage.nix
    ./networking.nix
    ./docker.nix
    ./frp.nix
    ./vault-agent.nix
    ./vault-unseal.nix
    ./backups.nix
    ./compose.nix
    ./tailscale-authkey.nix
  ];
}
