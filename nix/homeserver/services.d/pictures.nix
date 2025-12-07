{ config, ... }:
{
  name = "pictures";
  backup = {
    enable = true;
    paths = [ "${config.homeserver.mainDrive}/pictures" ];
  };
}
