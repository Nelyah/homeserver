{config, pkgs, lib, ...}: {
  name = "hugo_blog";
  compose = {
    enable = true;
    build = true;
    networks = ["frontend"];
    volumes = [];
  };
  files = {
    "Dockerfile".source = ./Dockerfile;
    "ssh_config".source = ./ssh_config;
  };
  secretFiles = {
    ".env" = {
      destination = ".env";
      template = ''
        {{ with secret "homeserver_secrets/data/hugo_blog" -}}
        API_TOKEN={{ .Data.data.HUGO_API_TOKEN }}
        {{ end -}}
      '';
    };
    "hugo-github-deploy-key" = {
      destination = "hugo-github-deploy-key";
      template = ''
        {{ with secret "homeserver_secrets/data/hugo_blog" -}}
        {{ .Data.data.SSH_PRIVATE_KEY }}
        {{ end -}}
      '';
    };
    "hugo-github-deploy-key.pub" = {
      destination = "hugo-github-deploy-key.pub";
      perms = "0644";
      template = ''
        {{ with secret "homeserver_secrets/data/hugo_blog" -}}
        {{ .Data.data.SSH_PUBLIC_KEY }}
        {{ end -}}
      '';
    };
  };
}
