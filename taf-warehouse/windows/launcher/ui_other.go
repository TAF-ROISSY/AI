//go:build !windows

package main

import (
	"fmt"
	"os/exec"
)

func alert(title, text string) { fmt.Printf("[%s] %s\n", title, text) }
func hideWindow(cmd *exec.Cmd) {}
