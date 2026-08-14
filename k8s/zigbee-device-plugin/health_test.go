package main

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestHealthStateBroadcastsTransitions(t *testing.T) {
	state := newHealthState("Unhealthy")
	_, first := state.snapshot()
	_, second := state.snapshot()

	if !state.set("Healthy") {
		t.Fatal("expected a health transition")
	}
	for name, changed := range map[string]<-chan struct{}{"first": first, "second": second} {
		select {
		case <-changed:
		case <-time.After(time.Second):
			t.Fatalf("%s watcher did not receive transition", name)
		}
	}
	if state.set("Healthy") {
		t.Fatal("setting the same health must not publish a transition")
	}
}

func TestValidateCharacterDevice(t *testing.T) {
	t.Run("accepts character device", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "device")
		if err := os.Symlink("/dev/null", path); err != nil {
			t.Fatal(err)
		}
		if err := validateCharacterDevice(path, "/dev", "null", false); err != nil {
			t.Fatalf("expected /dev/null to validate: %v", err)
		}
	})

	t.Run("rejects regular file", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "ttyUSB0")
		if err := os.WriteFile(path, []byte("not a device"), 0o600); err != nil {
			t.Fatal(err)
		}
		if err := validateCharacterDevice(path, dir, "ttyUSB", true); err == nil {
			t.Fatal("expected regular file to be rejected")
		}
	})

	t.Run("rejects path outside allowed directory", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "device")
		if err := os.Symlink("/dev/null", path); err != nil {
			t.Fatal(err)
		}
		if err := validateCharacterDevice(path, dir, "null", false); err == nil {
			t.Fatal("expected resolved path outside allowed directory to be rejected")
		}
	})

	t.Run("rejects non-numeric tty suffix", func(t *testing.T) {
		dir := t.TempDir()
		path := filepath.Join(dir, "ttyUSBx")
		if err := os.WriteFile(path, nil, 0o600); err != nil {
			t.Fatal(err)
		}
		if err := validateCharacterDevice(path, dir, "ttyUSB", true); err == nil {
			t.Fatal("expected non-numeric tty suffix to be rejected")
		}
	})
}
