{
  description = "Chloe's macOS Nix Configuration";

  inputs = {
    # TODO: Figure out a way to stay up to date with latest releases.

    # *-darwin here means that packages are tested for darwin compatibility
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-26.05-darwin";

    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixos-unstable";

    codex-cli-nix = {
      url = "github:sadjow/codex-cli-nix";
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };

    home-manager = {
      url = "github:nix-community/home-manager/release-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    codex-acp-nix = {
      url = "git+ssh://git@forgejo-ssh.forgejo.svc.k8s.nelyah.eu/Nelyah/codex-acp-nix.git?ref=main";
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };

    claude-agent-acp-nix = {
      url = "github:Nelyah/claude-agent-acp-nix";
      inputs.nixpkgs.follows = "nixpkgs-unstable";
    };

    nix-darwin = {
      # Use the default nix-darwin, following nixpkgs for compatibility
      url = "github:LnL7/nix-darwin/nix-darwin-26.05";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Pinned independently so neovim version is controlled separately from nixpkgs.
    # To upgrade: find the nixpkgs commit for the desired neovim version and update this URL.
    #
    # To find the commit, run this:
    # curl -s "https://api.github.com/repos/NixOS/nixpkgs/commits?path=pkgs/by-name/ne/neovim-unwrapped/package.nix&per_page=30" | jq -r '.[] | "\(.sha) \(.commit.message | split("\n")[0])"'

    # nvim 0.12.5
    nixpkgs-neovim.url = "github:NixOS/nixpkgs/6a96a4723c8e3e170b6a504a01d789d2bc3eeedf";
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    nix-darwin,
    home-manager,
    ...
  }: let
    darwinSystem = "aarch64-darwin";
    linuxSystem = "x86_64-linux";
    defaultGitUser = {
      name = "Nelyah";
      email = "contact@nelyah.eu";
    };
    gitConfigUserFor = gitUser: ''
      [user]
      	name = ${gitUser.name}
      	email = ${gitUser.email}
    '';
    defaultGitConfigUser = gitConfigUserFor defaultGitUser;
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

    neovimOverlay = system: {
      nixpkgs.overlays = [
        (_final: _prev: {
          neovim =
            (import inputs.nixpkgs-neovim {
              system = system;
              config.allowUnfree = true;
            }).neovim;
        })
      ];
    };

    mkDarwinHost = {
      hostname,
      username,
      hostPath,
      gitConfigUser ? defaultGitConfigUser,
    }:
      nix-darwin.lib.darwinSystem {
        system = darwinSystem;
        specialArgs = {
          inherit inputs username hostname;
        };
        modules = [
          (unstableOverlay darwinSystem)
          (neovimOverlay darwinSystem)
          {nixpkgs.overlays = [inputs.claude-agent-acp-nix.overlays.default];}
          hostPath
          ./modules/common.nix
          ./modules/darwin.nix
          home-manager.darwinModules.home-manager
          {
            home-manager = {
              useGlobalPkgs = true;
              useUserPackages = true;
              extraSpecialArgs = {inherit username gitConfigUser;};
            };
          }
        ];
      };

    mkNixosHost = {
      hostPath,
      gitUser ? defaultGitUser,
    }:
      nixpkgs.lib.nixosSystem {
        system = linuxSystem;
        specialArgs = {inherit inputs gitUser;};
        modules = [
          (unstableOverlay linuxSystem)
          (neovimOverlay linuxSystem)
          {nixpkgs.overlays = [inputs.claude-agent-acp-nix.overlays.default];}
          hostPath
          ./modules/common.nix
          ./modules/server.nix
          ./modules/tailscale.nix
        ];
      };
  in {
    darwinConfigurations.chloe-macbook-air = mkDarwinHost {
      hostname = "chloe-macbook-air";
      username = "chloe";
      hostPath = ./hosts/macbook-air;
    };

    darwinConfigurations.cdequeker-macbook-pro = mkDarwinHost {
      hostname = "cdequeker-macbook-pro";
      username = "cdequeker";
      hostPath = ./hosts/work-macbook;
      gitConfigUser = ''
        [include]
        	path = ~/.gitconfig-work-user
      '';
    };

    nixosConfigurations.home-stockholm = mkNixosHost {
      hostPath = ./hosts/home-stockholm;
    };

    nixosConfigurations.home-paris = mkNixosHost {
      hostPath = ./hosts/home-paris;
    };

    apps.${darwinSystem} = {
      default = {
        type = "app";
        meta.description = "Switch nix-darwin configuration";
        program = toString (
          nixpkgs.legacyPackages.${darwinSystem}.writeShellScript "switch" ''
            set -euo pipefail
            HOSTNAME=$(${nixpkgs.legacyPackages.${darwinSystem}.hostname}/bin/hostname)
            darwin-rebuild switch --flake ".#$HOSTNAME"
          ''
        );
      };

      ansible-deploy = {
        type = "app";
        meta.description = "Run Ansible playbook against Pi Zeros";
        program = toString (
          nixpkgs.legacyPackages.${darwinSystem}.writeShellScript "ansible-deploy" ''
            cd "$(${nixpkgs.legacyPackages.${darwinSystem}.git}/bin/git rev-parse --show-toplevel)/nix/ansible"
            ${
              nixpkgs.legacyPackages.${darwinSystem}.ansible
            }/bin/ansible-playbook -i inventory.yml site.yml "$@"
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
