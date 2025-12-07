{ config, ... }:
{
  name = "audiobook";
  backup = {
    enable = true;
    paths = [ "${config.homeserver.mainDrive}/audiobooks" ];
  };
}
