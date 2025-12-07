{ config, ... }:
{
  name = "hugo_blog";
  compose = {
    enable = true;
    path = "${config.homeserver.homeserverRoot}/services/blog_hugo/docker-compose.yml";
    networks = [ "frontend" ];
    volumes = [ ];
  };
}
