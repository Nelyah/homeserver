# Kubernetes Bootstrap

After switching the NixOS config, verify access:

```sh
kubectl get nodes
```

Apply the cluster-level resource folders:

```sh
./k8s/bootstrap.sh
```

The bootstrap step also installs `image-refresh`, a daily `04:00` CronJob that
checks registry-backed Deployment images and restarts only when a tag digest
changed. Deployments are included by default; set the Deployment label
`homeserver.nelyah.eu/image-refresh: "false"` to opt out.

Build and import local images used by Kubernetes manifests. The script discovers
`k8s/*/Dockerfile` contexts, imports changed images into k3s, and restarts
Deployments that reference changed local images:

```sh
./k8s/build-local-images.sh
```

Deploy all Helm releases with:

```sh
helmfile --file ./k8s/helmfile.yaml sync
```

Or run the full cluster sync:

```sh
./k8s/sync-cluster.sh
```
