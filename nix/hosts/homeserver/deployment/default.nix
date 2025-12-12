# Service deployment module
{ ... }: {
  imports = [
    ./files.nix
    ./secrets.nix
  ];
}
