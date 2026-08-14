package main

import (
	"context"
	"net"
	"os"
	"path/filepath"
	"testing"
	"time"

	"google.golang.org/grpc"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

func TestRemoveStaleSocketRefusesNonSocket(t *testing.T) {
	path := filepath.Join(t.TempDir(), "plugin.sock")
	if err := os.WriteFile(path, []byte("do not remove"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := removeStaleSocket(path); err == nil {
		t.Fatal("expected non-socket path to be rejected")
	}
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("non-socket path was removed: %v", err)
	}
}

func TestRemoveSocketIfOwnedChecksInode(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "plugin.sock")
	listener, err := net.Listen("unix", path)
	if err != nil {
		t.Fatal(err)
	}
	owned, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	listener.(*net.UnixListener).SetUnlinkOnClose(false)
	listener.Close()
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("replacement"), 0o600); err != nil {
		t.Fatal(err)
	}

	_ = removeSocketIfOwned(path, owned)
	if _, err := os.Stat(path); err != nil {
		t.Fatalf("replacement inode was removed: %v", err)
	}
}

type fakeRegistrationServer struct {
	pluginapi.UnimplementedRegistrationServer
	requests chan *pluginapi.RegisterRequest
}

func (s *fakeRegistrationServer) Register(_ context.Context, request *pluginapi.RegisterRequest) (*pluginapi.Empty, error) {
	s.requests <- request
	return &pluginapi.Empty{}, nil
}

func TestSupervisorReregistersWhenPluginSocketIsDeleted(t *testing.T) {
	dir := t.TempDir()
	kubeletSocket := filepath.Join(dir, "kubelet.sock")
	pluginSocket := filepath.Join(dir, "zigbee.sock")
	listener, err := net.Listen("unix", kubeletSocket)
	if err != nil {
		t.Fatal(err)
	}
	registration := &fakeRegistrationServer{requests: make(chan *pluginapi.RegisterRequest, 2)}
	kubeletServer := grpc.NewServer()
	pluginapi.RegisterRegistrationServer(kubeletServer, registration)
	go kubeletServer.Serve(listener)
	t.Cleanup(func() {
		kubeletServer.Stop()
		listener.Close()
	})

	cfg := supervisorConfig{
		kubeletSocket: kubeletSocket,
		pluginSocket:  pluginSocket,
		lockFile:      filepath.Join(dir, "plugin.lock"),
		resourceName:  "nelyah.eu/zigbee",
	}
	plugin := newDevicePlugin("device-id", "/dev/device", "/dev/zigbee", func() error { return nil })
	plugin.health.set(pluginapi.Healthy)
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- runSupervisor(ctx, cfg, plugin)
	}()

	first := waitForRegistration(t, registration.requests)
	assertRegistration(t, first)
	if err := os.Remove(pluginSocket); err != nil {
		t.Fatalf("simulate kubelet socket cleanup: %v", err)
	}
	second := waitForRegistration(t, registration.requests)
	assertRegistration(t, second)

	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("supervisor returned an error: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("supervisor did not stop after cancellation")
	}
	if _, err := os.Lstat(pluginSocket); !os.IsNotExist(err) {
		t.Fatalf("plugin socket was not cleaned up: %v", err)
	}
}

func waitForRegistration(t *testing.T, requests <-chan *pluginapi.RegisterRequest) *pluginapi.RegisterRequest {
	t.Helper()
	select {
	case request := <-requests:
		return request
	case <-time.After(5 * time.Second):
		t.Fatal("timed out waiting for kubelet registration")
		return nil
	}
}

func assertRegistration(t *testing.T, request *pluginapi.RegisterRequest) {
	t.Helper()
	if request.Version != pluginapi.Version || request.Endpoint != "zigbee.sock" || request.ResourceName != "nelyah.eu/zigbee" {
		t.Fatalf("unexpected registration request: %#v", request)
	}
	if request.Options == nil || request.Options.PreStartRequired || request.Options.GetPreferredAllocationAvailable {
		t.Fatalf("unexpected registration options: %#v", request.Options)
	}
}
