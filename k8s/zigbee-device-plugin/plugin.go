package main

import (
	"context"
	"fmt"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

type devicePlugin struct {
	pluginapi.UnimplementedDevicePluginServer

	deviceID      string
	hostPath      string
	containerPath string
	probe         func() error
	health        *healthState
}

func newDevicePlugin(deviceID, hostPath, containerPath string, probe func() error) *devicePlugin {
	return &devicePlugin{
		deviceID:      deviceID,
		hostPath:      hostPath,
		containerPath: containerPath,
		probe:         probe,
		health:        newHealthState(pluginapi.Unhealthy),
	}
}

func (p *devicePlugin) GetDevicePluginOptions(context.Context, *pluginapi.Empty) (*pluginapi.DevicePluginOptions, error) {
	return &pluginapi.DevicePluginOptions{
		PreStartRequired:                false,
		GetPreferredAllocationAvailable: false,
	}, nil
}

func (p *devicePlugin) ListAndWatch(_ *pluginapi.Empty, stream grpc.ServerStreamingServer[pluginapi.ListAndWatchResponse]) error {
	for {
		health, changed := p.health.snapshot()
		response := &pluginapi.ListAndWatchResponse{
			Devices: []*pluginapi.Device{{ID: p.deviceID, Health: health}},
		}
		if err := stream.Send(response); err != nil {
			return err
		}

		select {
		case <-stream.Context().Done():
			return nil
		case <-changed:
		}
	}
}

func (p *devicePlugin) Allocate(_ context.Context, request *pluginapi.AllocateRequest) (*pluginapi.AllocateResponse, error) {
	if request == nil {
		return nil, status.Error(codes.InvalidArgument, "allocation request is nil")
	}
	if len(request.ContainerRequests) != 1 {
		return nil, status.Errorf(codes.InvalidArgument, "expected exactly one container request, got %d", len(request.ContainerRequests))
	}

	ids := request.ContainerRequests[0].DevicesIds
	if len(ids) != 1 {
		return nil, status.Errorf(codes.InvalidArgument, "expected exactly one device ID, got %d", len(ids))
	}
	if ids[0] != p.deviceID {
		return nil, status.Errorf(codes.InvalidArgument, "unknown device ID %q", ids[0])
	}

	health, _ := p.health.snapshot()
	if health != pluginapi.Healthy {
		return nil, status.Error(codes.FailedPrecondition, "zigbee device is unhealthy")
	}
	if err := p.probe(); err != nil {
		p.health.set(pluginapi.Unhealthy)
		return nil, status.Error(codes.FailedPrecondition, fmt.Sprintf("zigbee device validation failed: %v", err))
	}

	return &pluginapi.AllocateResponse{
		ContainerResponses: []*pluginapi.ContainerAllocateResponse{{
			Devices: []*pluginapi.DeviceSpec{{
				HostPath:      p.hostPath,
				ContainerPath: p.containerPath,
				Permissions:   "rw",
			}},
		}},
	}, nil
}
