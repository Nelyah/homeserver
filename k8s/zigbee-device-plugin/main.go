package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"syscall"
	"time"

	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

const (
	defaultResourceName        = "nelyah.eu/zigbee"
	defaultDeviceID            = "7cfb165fcd8aef11922220ccef8776e9"
	defaultHostDevicePath      = "/dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_7cfb165fcd8aef11922220ccef8776e9-if00-port0"
	defaultHealthDevicePath    = "/host-dev/serial/by-id/usb-ITead_Sonoff_Zigbee_3.0_USB_Dongle_Plus_7cfb165fcd8aef11922220ccef8776e9-if00-port0"
	defaultContainerDevicePath = "/dev/zigbee"
	defaultPluginSocketName    = "nelyah-zigbee.sock"
	defaultLockFileName        = "nelyah-zigbee.lock"
)

func environmentOrDefault(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	resourceName := environmentOrDefault("DEVICE_PLUGIN_RESOURCE_NAME", defaultResourceName)
	deviceID := environmentOrDefault("DEVICE_PLUGIN_DEVICE_ID", defaultDeviceID)
	hostDevicePath := environmentOrDefault("DEVICE_PLUGIN_HOST_PATH", defaultHostDevicePath)
	healthDevicePath := environmentOrDefault("DEVICE_PLUGIN_HEALTH_PATH", defaultHealthDevicePath)
	containerDevicePath := environmentOrDefault("DEVICE_PLUGIN_CONTAINER_PATH", defaultContainerDevicePath)
	pluginSocketName := environmentOrDefault("DEVICE_PLUGIN_SOCKET_NAME", defaultPluginSocketName)
	lockFileName := environmentOrDefault("DEVICE_PLUGIN_LOCK_NAME", defaultLockFileName)

	cfg := supervisorConfig{
		kubeletSocket: pluginapi.KubeletSocket,
		pluginSocket:  filepath.Join(pluginapi.DevicePluginPath, pluginSocketName),
		lockFile:      filepath.Join(pluginapi.DevicePluginPath, lockFileName),
		resourceName:  resourceName,
	}

	probe := func() error {
		return validateCharacterDevice(healthDevicePath, "/host-dev", "ttyUSB", true)
	}
	plugin := newDevicePlugin(deviceID, hostDevicePath, containerDevicePath, probe)
	plugin.refreshHealth()
	go plugin.monitorHealth(ctx, 2*time.Second)

	if err := runSupervisor(ctx, cfg, plugin); err != nil {
		log.Fatalf("zigbee device plugin stopped: %v", err)
	}
}
