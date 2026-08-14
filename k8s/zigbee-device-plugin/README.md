# Zigbee device plugin

This is a purpose-built Kubernetes device plugin for the single SONOFF Zigbee
coordinator attached to `home-stockholm`. Device identity, host path, and the
container path `/dev/zigbee` are compiled into the binary.

The image is deliberately excluded from `build-local-images.sh`: its Dockerfile
is named `Dockerfile.manual`, the builder image is pinned by digest, and the
DaemonSet uses `imagePullPolicy: Never` with an `OnDelete` update strategy.

Build, test, and import the image explicitly:

```sh
cd /data/homeserver/k8s/zigbee-device-plugin
go test -race ./...
./build-image.sh v1
```

The script uses Docker directly when the current user can access it. Importing
into k3s may still prompt once for `sudo` because its containerd socket is
root-only. Image tags are immutable after import, so use a new tag for every
reviewed build.

Deploy both device-plugin releases before Home Assistant and verify both
resources are allocatable:

```sh
cd /data/homeserver/k8s
helmfile --file helmfile.yaml --selector name=zigbee-device-plugin sync
helmfile --file helmfile.yaml --selector name=thread-device-plugin sync
kubectl get node home-stockholm \
  --template='zigbee={{ index .status.allocatable "nelyah.eu/zigbee" }} thread={{ index .status.allocatable "nelyah.eu/thread" }}{{ "\n" }}'
```

For a reviewed plugin update, choose a new tag, pass it to `build-image.sh`,
update `values.yaml`, sync both releases, and explicitly delete the existing
DaemonSet pods. Kubernetes does not replace `OnDelete` DaemonSet pods
automatically.
