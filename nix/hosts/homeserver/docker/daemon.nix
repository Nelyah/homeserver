# Docker daemon configuration
{
  pkgs,
  config,
  ...
}: {
  virtualisation.docker = {
    enable = true;
    enableOnBoot = true;
    daemon.settings = {
      "data-root" = config.homeserver.paths.dockerDataRoot;
      "log-driver" = "journald";
    };
  };

  environment.systemPackages = [
    pkgs.docker-compose
  ];
}
