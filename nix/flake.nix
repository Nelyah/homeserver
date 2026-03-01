{
  description = "Chloe's macOS Nix Configuration";

  inputs = {
    # TODO: Figure out a way to stay up to date with latest releases. 

    # *-darwin here means that packages are tested for darwin compatibility
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
      url = "github:LnL7/nix-darwin/nix-darwin-25.11";
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
    darwinSystem = "aarch64-darwin";
    linuxSystem = "x86_64-linux";
    # Shared overlay that makes nixpkgs-unstable available as pkgs.unstable
    unstableOverlay = system: {
      nixpkgs.overlays = [
        (_final: prev: {
          unstable = import inputs.nixpkgs-unstable {
            system = system;
            config = prev.config;
          };
        })
      ];
    };
  in {
    darwinConfigurations.${hostname} = nix-darwin.lib.darwinSystem {
      system = darwinSystem;
      specialArgs = {inherit inputs username hostname;};
      modules = [
        (unstableOverlay darwinSystem)
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

    nixosConfigurations.home-stockholm = nixpkgs.lib.nixosSystem {
      system = linuxSystem;
      specialArgs = {inherit inputs;};
      modules = [
        (unstableOverlay linuxSystem)
        ./hosts/home-stockholm
        ./modules/common.nix
        ./modules/server.nix
        ./modules/tailscale.nix
      ];
    };

    nixosConfigurations.home-paris = nixpkgs.lib.nixosSystem {
      system = linuxSystem;
      specialArgs = {inherit inputs;};
      modules = [
        (unstableOverlay linuxSystem)
        ./hosts/home-paris
        ./modules/common.nix
        ./modules/server.nix
        ./modules/tailscale.nix
      ];
    };

    apps.${darwinSystem} = {
      default = {
        type = "app";
        meta.description = "Switch nix-darwin configuration";
        program = toString (
          nixpkgs.legacyPackages.${darwinSystem}.writeShellScript "switch" ''
            darwin-rebuild switch --flake .#${hostname}
          ''
        );
      };

      ansible-deploy = {
        type = "app";
        meta.description = "Run Ansible playbook against Pi Zeros";
        program = toString (
          nixpkgs.legacyPackages.${darwinSystem}.writeShellScript "ansible-deploy" ''
            cd "$(${nixpkgs.legacyPackages.${darwinSystem}.git}/bin/git rev-parse --show-toplevel)/ansible"
            ${nixpkgs.legacyPackages.${darwinSystem}.ansible}/bin/ansible-playbook -i inventory.yml site.yml "$@"
          ''
        );
      };
    };

    apps.${linuxSystem} = {
      default = {
        type = "app";
        meta.description = "Switch NixOS configuration";
        program = toString (
          nixpkgs.legacyPackages.${linuxSystem}.writeShellScript "switch" ''
            set -euo pipefail
            HOSTNAME=$(${nixpkgs.legacyPackages.${linuxSystem}.hostname}/bin/hostname)
            nixos-rebuild switch --flake ".#$HOSTNAME"
          ''
        );
      };
    };

  };
}
