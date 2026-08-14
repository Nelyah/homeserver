package main

import (
	"context"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	pluginapi "k8s.io/kubelet/pkg/apis/deviceplugin/v1beta1"
)

type healthState struct {
	mu      sync.Mutex
	health  string
	changed chan struct{}
}

func newHealthState(initial string) *healthState {
	return &healthState{
		health:  initial,
		changed: make(chan struct{}),
	}
}

func (s *healthState) snapshot() (string, <-chan struct{}) {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.health, s.changed
}

func (s *healthState) set(health string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if health == s.health {
		return false
	}
	s.health = health
	close(s.changed)
	s.changed = make(chan struct{})
	return true
}

func validateCharacterDevice(path, allowedDir, basenamePrefix string, numericSuffix bool) error {
	resolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return fmt.Errorf("resolve %s: %w", path, err)
	}
	resolved = filepath.Clean(resolved)
	if filepath.Dir(resolved) != filepath.Clean(allowedDir) {
		return fmt.Errorf("resolved device %s is outside %s", resolved, allowedDir)
	}

	name := filepath.Base(resolved)
	if !strings.HasPrefix(name, basenamePrefix) {
		return fmt.Errorf("resolved device %s does not start with %s", name, basenamePrefix)
	}
	if numericSuffix {
		suffix := strings.TrimPrefix(name, basenamePrefix)
		if suffix == "" {
			return fmt.Errorf("resolved device %s has no numeric suffix", name)
		}
		for _, r := range suffix {
			if r < '0' || r > '9' {
				return fmt.Errorf("resolved device %s has a non-numeric suffix", name)
			}
		}
	}

	info, err := os.Stat(resolved)
	if err != nil {
		return fmt.Errorf("stat %s: %w", resolved, err)
	}
	if info.Mode()&os.ModeCharDevice == 0 {
		return fmt.Errorf("resolved device %s is not a character device", resolved)
	}
	return nil
}

func (p *devicePlugin) refreshHealth() {
	health := pluginapi.Healthy
	if err := p.probe(); err != nil {
		health = pluginapi.Unhealthy
	}
	if p.health.set(health) {
		log.Printf("device %s health changed to %s", p.deviceID, health)
	}
}

func (p *devicePlugin) monitorHealth(ctx context.Context, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			p.refreshHealth()
		}
	}
}
