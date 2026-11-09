//go:build windows

package main

import (
	"os/exec"
	"syscall"
	"unsafe"
)

func alert(title, text string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	t, _ := syscall.UTF16PtrFromString(title)
	m, _ := syscall.UTF16PtrFromString(text)
	user32.NewProc("MessageBoxW").Call(0, uintptr(unsafe.Pointer(m)), uintptr(unsafe.Pointer(t)), 0x40) // MB_ICONINFORMATION
}

// Le serveur Python tourne sans fenêtre noire.
func hideWindow(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000} // CREATE_NO_WINDOW
}
