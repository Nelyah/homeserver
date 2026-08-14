package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"path/filepath"
	"time"

	"golang.org/x/sys/unix"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

var (
	errRestartServer     = errors.New("restart device plugin server")
	errFatalRegistration = errors.New("fatal kubelet registration error")
)

type supervisorConfig struct {
	kubeletSocket string
	pluginSocket  string
	lockFile      string
	resourceName  string
}

func runSupervisor(ctx context.Context, cfg supervisorConfig, plugin *devicePlugin) error {
	lock, err := acquireLock(cfg.lockFile)
	if err != nil {
		return err
	}
	defer releaseLock(lock)

	for {
		err := serveCycle(ctx, cfg, plugin)
		if ctx.Err() != nil {
			return nil
		}
		if errors.Is(err, errFatalRegistration) {
			return err
		}
		log.Printf("restarting device plugin server: %v", err)
		select {
		case <-ctx.Done():
			return nil
		case <-time.After(250 * time.Millisecond):
		}
	}
}

func acquireLock(path string) (*os.File, error) {
	file, err := os.OpenFile(path, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return nil, fmt.Errorf("open lock file %s: %w", path, err)
	}
	if err := unix.Flock(int(file.Fd()), unix.LOCK_EX|unix.LOCK_NB); err != nil {
		file.Close()
		return nil, fmt.Errorf("acquire lock %s: %w", path, err)
	}
	return file, nil
}

func releaseLock(file *os.File) {
	if file == nil {
		return
	}
	_ = unix.Flock(int(file.Fd()), unix.LOCK_UN)
	_ = file.Close()
}

func serveCycle(ctx context.Context, cfg supervisorConfig, plugin *devicePlugin) error {
	if err := removeStaleSocket(cfg.pluginSocket); err != nil {
		return err
	}

	listener, err := net.Listen("unix", cfg.pluginSocket)
	if err != nil {
		return fmt.Errorf("listen on %s: %w", cfg.pluginSocket, err)
	}
	unixListener, ok := listener.(*net.UnixListener)
	if !ok {
		listener.Close()
		return fmt.Errorf("listener for %s is not a Unix listener", cfg.pluginSocket)
	}
	// Let the inode-aware cleanup below remove only the socket we created.
	unixListener.SetUnlinkOnClose(false)
	createdSocket, err := os.Lstat(cfg.pluginSocket)
	if err != nil {
		listener.Close()
		return fmt.Errorf("stat created socket %s: %w", cfg.pluginSocket, err)
	}

	server := grpc.NewServer()
	pluginapi.RegisterDevicePluginServer(server, plugin)
	serveErr := make(chan error, 1)
	go func() {
		serveErr <- server.Serve(listener)
	}()

	defer func() {
		server.Stop()
		_ = listener.Close()
		if err := removeSocketIfOwned(cfg.pluginSocket, createdSocket); err != nil {
			log.Printf("socket cleanup failed: %v", err)
		}
	}()

	if err := verifyPluginServer(ctx, cfg.pluginSocket); err != nil {
		return fmt.Errorf("verify plugin gRPC server: %w", err)
	}
	kubeletSocket, err := waitAndRegister(ctx, cfg)
	if err != nil {
		return err
	}
	log.Printf("registered %s with kubelet", cfg.resourceName)

	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return nil
		case err := <-serveErr:
			if err == nil || errors.Is(err, grpc.ErrServerStopped) {
				return errRestartServer
			}
			return fmt.Errorf("gRPC server stopped: %w", err)
		case <-ticker.C:
			if !sameFile(cfg.pluginSocket, createdSocket) {
				return fmt.Errorf("%w: plugin socket was removed or replaced", errRestartServer)
			}
			if !sameFile(cfg.kubeletSocket, kubeletSocket) {
				return fmt.Errorf("%w: kubelet socket was removed or replaced", errRestartServer)
			}
		}
	}
}

func removeStaleSocket(path string) error {
	info, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect existing socket %s: %w", path, err)
	}
	if info.Mode()&os.ModeSocket == 0 {
		return fmt.Errorf("refusing to remove non-socket path %s", path)
	}
	if err := os.Remove(path); err != nil {
		return fmt.Errorf("remove stale socket %s: %w", path, err)
	}
	return nil
}

func removeSocketIfOwned(path string, owned os.FileInfo) error {
	current, err := os.Lstat(path)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return fmt.Errorf("inspect socket %s during cleanup: %w", path, err)
	}
	if !os.SameFile(owned, current) {
		return nil
	}
	if current.Mode()&os.ModeSocket == 0 {
		return fmt.Errorf("owned path %s is no longer a socket", path)
	}
	if err := os.Remove(path); err != nil {
		return fmt.Errorf("remove socket %s: %w", path, err)
	}
	return nil
}

func sameFile(path string, expected os.FileInfo) bool {
	current, err := os.Lstat(path)
	return err == nil && os.SameFile(expected, current)
}

func verifyPluginServer(parent context.Context, socket string) error {
	ctx, cancel := context.WithTimeout(parent, 3*time.Second)
	defer cancel()
	connection, err := newUnixClient(socket)
	if err != nil {
		return err
	}
	defer connection.Close()
	_, err = pluginapi.NewDevicePluginClient(connection).GetDevicePluginOptions(ctx, &pluginapi.Empty{})
	return err
}

func waitAndRegister(ctx context.Context, cfg supervisorConfig) (os.FileInfo, error) {
	backoff := 250 * time.Millisecond
	for {
		info, err := os.Lstat(cfg.kubeletSocket)
		if err == nil && info.Mode()&os.ModeSocket != 0 {
			err = registerWithKubelet(ctx, cfg)
			if err == nil {
				current, statErr := os.Lstat(cfg.kubeletSocket)
				if statErr == nil {
					return current, nil
				}
				err = statErr
			} else if !isTransientRegistrationError(err) {
				return nil, fmt.Errorf("%w: %v", errFatalRegistration, err)
			}
		}

		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		log.Printf("waiting for kubelet registration endpoint: %v", err)
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-time.After(backoff):
		}
		if backoff < 5*time.Second {
			backoff *= 2
			if backoff > 5*time.Second {
				backoff = 5 * time.Second
			}
		}
	}
}

func registerWithKubelet(parent context.Context, cfg supervisorConfig) error {
	ctx, cancel := context.WithTimeout(parent, 5*time.Second)
	defer cancel()
	connection, err := newUnixClient(cfg.kubeletSocket)
	if err != nil {
		return err
	}
	defer connection.Close()

	_, err = pluginapi.NewRegistrationClient(connection).Register(ctx, &pluginapi.RegisterRequest{
		Version:      pluginapi.Version,
		Endpoint:     filepath.Base(cfg.pluginSocket),
		ResourceName: cfg.resourceName,
		Options: &pluginapi.DevicePluginOptions{
			PreStartRequired:                false,
			GetPreferredAllocationAvailable: false,
		},
	})
	return err
}

func isTransientRegistrationError(err error) bool {
	switch status.Code(err) {
	case codes.Unavailable, codes.DeadlineExceeded:
		return true
	default:
		return false
	}
}

func newUnixClient(socket string) (*grpc.ClientConn, error) {
	return grpc.NewClient(
		"passthrough:///unix",
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return (&net.Dialer{}).DialContext(ctx, "unix", socket)
		}),
	)
}
