{
  description = "Chloe's macOS Nix Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";

    home-manager = {
      url = "github:nix-community/home-manager/release-25.11";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    nix-darwin = {
      # Use the default nix-darwin, following nixpkgs for compatibility
      url = "github:LnL7/nix-darwin";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    nix-darwin,
    home-manager,
    ...
  }: let
    username = "chloe";
    hostname = "chloe-macbook-air";
    system = "aarch64-darwin";
  in {
    darwinConfigurations.${hostname} = nix-darwin.lib.darwinSystem {
      inherit system;
      specialArgs = {inherit inputs username hostname;};
      modules = [
        ./darwin
        home-manager.darwinModules.home-manager
        {
          home-manager = {
            useGlobalPkgs = true;
            useUserPackages = true;
            extraSpecialArgs = {inherit username;};
            users.${username} = import ./home;
          };
        }

      ];
    };

    # Convenience output for `nix run .#switch`
    apps.${system}.default = {
      type = "app";
      program = toString (nixpkgs.legacyPackages.${system}.writeShellScript "switch" ''
        darwin-rebuild switch --flake .#${hostname}
      '');
    };
  };
}
