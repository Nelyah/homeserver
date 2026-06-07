{
  pkgs,
  config,
  ...
}: {
  services.k3s = {
    enable = true;
    role = "server";
    clusterInit = true;
    extraFlags = [
      "--disable=traefik"
      "--disable=servicelb"
      "--write-kubeconfig-mode=0644"
      "--default-local-storage-path=${config.homeserver.mainDrive}/k3s/storage"
    ];
  };

  environment.systemPackages = with pkgs; [
    helmfile
    k3s
    kubectl
    kubernetes-helm
  ];
}
