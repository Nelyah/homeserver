{
  description = "Chloe's macOS Nix Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-25.11-darwin";

    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

    codex-cli-nix = {
      url = "github:sadjow/codex-cli-nix";
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };

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
    homeserverSystem = "x86_64-linux";
  in {
    darwinConfigurations.${hostname} = nix-darwin.lib.darwinSystem {
      inherit system;
      specialArgs = {inherit inputs username hostname;};
      modules = [
        ./hosts/macbook-air
        ./modules/common.nix
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
      meta.description = "Switch nix-darwin configuration";
      program = toString (
        nixpkgs.legacyPackages.${system}.writeShellScript "switch" ''
          darwin-rebuild switch --flake .#${hostname}
        ''
      );
    };

    nixosConfigurations.home-stockholm = nixpkgs.lib.nixosSystem {
      system = homeserverSystem;
      specialArgs = {inherit inputs;};
      modules = [
        {
          # With nixpkgs.overlay, the resulting attribute set is merged
          # into `pkgs.` before we proceed further
          nixpkgs.overlays = [
            (_final: prev: {
              unstable = import inputs.nixpkgs-unstable {
                system = homeserverSystem;
                config = prev.config;
              };
            })
          ];
        }
        ./hosts/home-stockholm
        ./modules/common.nix
        ./modules/server.nix
        ./modules/tailscale.nix
      ];
    };

    nixosConfigurations.home-paris = nixpkgs.lib.nixosSystem {
      system = homeserverSystem;
      specialArgs = {inherit inputs;};
      modules = [
        {
          nixpkgs.overlays = [
            (_final: prev: {
              unstable = import inputs.nixpkgs-unstable {
                system = homeserverSystem;
                config = prev.config;
              };
            })
          ];
        }
        ./hosts/home-paris
        ./modules/common.nix
        ./modules/server.nix
        ./modules/tailscale.nix
      ];
    };
  };
}
