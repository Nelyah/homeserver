package main

import (
	"context"
	"errors"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

func TestAllocateValidation(t *testing.T) {
	probeErr := error(nil)
	plugin := newDevicePlugin("device-id", "/dev/serial/by-id/device", "/dev/zigbee", func() error {
		return probeErr
	})
	plugin.health.set(pluginapi.Healthy)

	tests := []struct {
		name    string
		request *pluginapi.AllocateRequest
		code    codes.Code
	}{
		{name: "nil request", request: nil, code: codes.InvalidArgument},
		{name: "no container", request: &pluginapi.AllocateRequest{}, code: codes.InvalidArgument},
		{
			name: "multiple containers",
			request: &pluginapi.AllocateRequest{ContainerRequests: []*pluginapi.ContainerAllocateRequest{
				{DevicesIds: []string{"device-id"}},
				{DevicesIds: []string{"device-id"}},
			}},
			code: codes.InvalidArgument,
		},
		{
			name: "no device ID",
			request: &pluginapi.AllocateRequest{ContainerRequests: []*pluginapi.ContainerAllocateRequest{
				{},
			}},
			code: codes.InvalidArgument,
		},
		{
			name: "multiple device IDs",
			request: &pluginapi.AllocateRequest{ContainerRequests: []*pluginapi.ContainerAllocateRequest{
				{DevicesIds: []string{"device-id", "device-id"}},
			}},
			code: codes.InvalidArgument,
		},
		{
			name: "unknown device ID",
			request: &pluginapi.AllocateRequest{ContainerRequests: []*pluginapi.ContainerAllocateRequest{
				{DevicesIds: []string{"other"}},
			}},
			code: codes.InvalidArgument,
		},
	}

	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := plugin.Allocate(context.Background(), test.request)
			if status.Code(err) != test.code {
				t.Fatalf("got %s, want %s: %v", status.Code(err), test.code, err)
			}
		})
	}

	plugin.health.set(pluginapi.Unhealthy)
	validRequest := allocationRequest("device-id")
	if _, err := plugin.Allocate(context.Background(), validRequest); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("unhealthy allocation got %s, want %s", status.Code(err), codes.FailedPrecondition)
	}

	plugin.health.set(pluginapi.Healthy)
	probeErr = errors.New("device disappeared")
	if _, err := plugin.Allocate(context.Background(), validRequest); status.Code(err) != codes.FailedPrecondition {
		t.Fatalf("failed fresh probe got %s, want %s", status.Code(err), codes.FailedPrecondition)
	}
	health, _ := plugin.health.snapshot()
	if health != pluginapi.Unhealthy {
		t.Fatalf("fresh probe failure did not mark device unhealthy: %s", health)
	}
}

func TestAllocateReturnsOnlyExpectedDevice(t *testing.T) {
	plugin := newDevicePlugin("device-id", "/dev/serial/by-id/device", "/dev/zigbee", func() error { return nil })
	plugin.health.set(pluginapi.Healthy)

	response, err := plugin.Allocate(context.Background(), allocationRequest("device-id"))
	if err != nil {
		t.Fatal(err)
	}
	if len(response.ContainerResponses) != 1 {
		t.Fatalf("got %d container responses", len(response.ContainerResponses))
	}
	container := response.ContainerResponses[0]
	if len(container.Devices) != 1 {
		t.Fatalf("got %d device specs", len(container.Devices))
	}
	device := container.Devices[0]
	if device.HostPath != "/dev/serial/by-id/device" || device.ContainerPath != "/dev/zigbee" || device.Permissions != "rw" {
		t.Fatalf("unexpected device spec: %#v", device)
	}
	if len(container.Envs) != 0 || len(container.Mounts) != 0 || len(container.Annotations) != 0 || len(container.CdiDevices) != 0 {
		t.Fatalf("allocation response contains unexpected additions: %#v", container)
	}
}

func allocationRequest(id string) *pluginapi.AllocateRequest {
	return &pluginapi.AllocateRequest{ContainerRequests: []*pluginapi.ContainerAllocateRequest{{DevicesIds: []string{id}}}}
}

type captureListAndWatchStream struct {
	grpc.ServerStream
	ctx       context.Context
	responses chan *pluginapi.ListAndWatchResponse
}

func (s *captureListAndWatchStream) Context() context.Context {
	return s.ctx
}

func (s *captureListAndWatchStream) Send(response *pluginapi.ListAndWatchResponse) error {
	select {
	case s.responses <- response:
		return nil
	case <-s.ctx.Done():
		return s.ctx.Err()
	}
}

func TestListAndWatchPublishesInitialStateAndTransitions(t *testing.T) {
	plugin := newDevicePlugin("device-id", "/dev/device", "/dev/zigbee", func() error { return nil })
	ctx, cancel := context.WithCancel(context.Background())
	stream := &captureListAndWatchStream{
		ctx:       ctx,
		responses: make(chan *pluginapi.ListAndWatchResponse, 2),
	}
	done := make(chan error, 1)
	go func() {
		done <- plugin.ListAndWatch(&pluginapi.Empty{}, stream)
	}()

	assertHealthResponse(t, stream.responses, pluginapi.Unhealthy)
	plugin.health.set(pluginapi.Healthy)
	assertHealthResponse(t, stream.responses, pluginapi.Healthy)
	cancel()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("ListAndWatch returned an error: %v", err)
		}
	case <-time.After(time.Second):
		t.Fatal("ListAndWatch did not stop after cancellation")
	}
}

func assertHealthResponse(t *testing.T, responses <-chan *pluginapi.ListAndWatchResponse, expected string) {
	t.Helper()
	select {
	case response := <-responses:
		if len(response.Devices) != 1 || response.Devices[0].ID != "device-id" || response.Devices[0].Health != expected {
			t.Fatalf("unexpected health response: %#v", response)
		}
	case <-time.After(time.Second):
		t.Fatalf("timed out waiting for %s health", expected)
	}
}
