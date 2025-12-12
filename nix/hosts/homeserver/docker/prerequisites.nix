# Create external Docker networks and volumes for compose stacks
{
  pkgs,
  lib,
  config,
  ...
}: let
  homeserverLib = import ../lib { inherit lib; };

  # Read services from config (populated by services.nix module)
  services = config.homeserver.services;
  enabledCompose = homeserverLib.docker.filterEnabledCompose services;

  networks = homeserverLib.docker.collectNetworks enabledCompose;
  volumes = homeserverLib.docker.collectVolumes enabledCompose;
in {
  # Create external networks/volumes referenced by compose stacks
  system.activationScripts.dockerPrereqs.text =
    homeserverLib.docker.mkPrereqScript {
      dockerBin = "${pkgs.docker}/bin/docker";
      inherit networks volumes;
    };
}
