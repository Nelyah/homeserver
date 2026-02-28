{
  pkgs,
  config,
  inputs,
  ...
}: {
  users.users.chloe = {
    isNormalUser = true;
    extraGroups = ["wheel" "docker" "data"];
    shell = pkgs.zsh;
  };

  users.users.root.shell = pkgs.zsh;

  time.timeZone = "Europe/Stockholm";

  # Homeserver-specific packages (common packages are in modules/common.nix)
  environment.systemPackages =
    (with pkgs; [
      # System tools
      bash
      gcc
      gdb
      net-tools
      ethtool
      duf
      smartmontools
      davfs2

      # Backup & sync
      restic

      # Email
      isync
      msmtp
      neomutt
      notmuch

	      # Media
	      beets
	
	      # Development
	      python3Packages.pip
	    ])
	    ++ [inputs.codex-cli-nix.packages.${pkgs.stdenv.hostPlatform.system}.default];

  environment.variables = {
    EDITOR = "nvim";
    VISUAL = "nvim";
    CARGO_HOME = "$HOME/.cargo";
    RUSTUP_HOME = "$HOME/.rustup";
    GOPATH = "$HOME/.local/share/go";
  };

  environment.shellInit = ''
    git_repo_path=${config.homeserver.homeserverRoot}
    services_directory="${"$"}{git_repo_path}/services"
    export PATH="${"$"}{git_repo_path}/bin:${"$"}{PATH}"
    alias cdd="cd ${"$"}{git_repo_path}"
    alias cddd="cd ${"$"}{services_directory}"
    alias cdn="cd ${"$"}{services_directory}/nextcloud"
    alias cdw="cd ${"$"}{services_directory}/wordpress"

    if [ -n "${"$"}{ZSH_VERSION-}" ]; then
      case "$-" in
        *i*)
	          __svc_completion_precmd() {
	            if type compdef >/dev/null 2>&1 && command -v svc >/dev/null 2>&1; then
	              eval "$(_SVC_COMPLETE=zsh_source svc)"
	
	              add-zsh-hook -d precmd __svc_completion_precmd >/dev/null 2>&1 || :
	              unfunction __svc_completion_precmd >/dev/null 2>&1 || :
	            fi
	          }

          autoload -Uz add-zsh-hook >/dev/null 2>&1 || :
	          add-zsh-hook precmd __svc_completion_precmd >/dev/null 2>&1 || :
	        ;;
	      esac
	    fi
	  '';

  system.stateVersion = "25.11";
}
