# Docker infrastructure module
{ ... }: {
  imports = [
    ./daemon.nix
    ./prerequisites.nix
    ./maintenance.nix
  ];
}
