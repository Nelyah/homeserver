{...}: {
  imports = [
    ./boot.nix
    ./hardware-configuration.nix
    ./options.nix
    ./services.nix           # Must come after options.nix
    ./base.nix
    ./storage.nix
    ./networking.nix
    ./docker                 # Split from docker.nix
    ./deployment             # Split from deployment.nix
    ./frp.nix
    ./vault-agent.nix
    ./vault-unseal.nix
    ./backup                 # Reorganized with default.nix
    ./compose                # Split from compose.nix
    ./disk-health.nix        # SMART disk health monitoring
    ./geoip-updater.nix      # Weekly GeoIP database updates for Caddy
  ];
}
