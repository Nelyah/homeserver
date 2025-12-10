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
    ./backup/backup.nix
    ./backup/maintenance.nix
    ./compose.nix
  ];
}
