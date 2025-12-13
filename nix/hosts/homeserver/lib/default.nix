# Re-export all lib functions
# Usage: homeserverLib = import ./lib { inherit lib; };
#        homeserverLib.docker.collectNetworks services
{ lib }:

{
  deployment = import ./deployment.nix { inherit lib; };
  docker = import ./docker.nix { inherit lib; };
}
