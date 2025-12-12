# Docker daemon configuration
{
  pkgs,
  config,
  ...
}: {
  virtualisation.docker = {
    enable = true;
    enableOnBoot = true;
    daemon.settings."data-root" = config.homeserver.paths.dockerDataRoot;
  };

  environment.systemPackages = [
    pkgs.docker-compose
  ];
}
