# Re-export all lib functions
# Usage: homeserverLib = import ./lib { inherit lib; };
#        homeserverLib.backup.mkForgetFlags policy
#        homeserverLib.docker.collectNetworks services
{ lib }:

{
  backup = import ./backup.nix { inherit lib; };
  deployment = import ./deployment.nix { inherit lib; };
  docker = import ./docker.nix { inherit lib; };
}
