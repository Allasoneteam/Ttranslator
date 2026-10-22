//go:build windows

package main

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"unsafe"
)

var (
	kernel32                     = syscall.NewLazyDLL("kernel32.dll")
	user32                       = syscall.NewLazyDLL("user32.dll")
	procCreateJobObjectW         = kernel32.NewProc("CreateJobObjectW")
	procSetInformationJobObject  = kernel32.NewProc("SetInformationJobObject")
	procAssignProcessToJobObject = kernel32.NewProc("AssignProcessToJobObject")
	procGlobalMemoryStatusEx     = kernel32.NewProc("GlobalMemoryStatusEx")
	procSetErrorMode             = kernel32.NewProc("SetErrorMode")
	procMessageBoxW              = user32.NewProc("MessageBoxW")
)

const (
	createNoWindow                    = 0x08000000
	jobObjectExtendedLimitInformation = 9
	jobObjectLimitKillOnJobClose      = 0x2000
	processSetQuota                   = 0x0100
	processTerminate                  = 0x0001
	semFailCriticalErrors             = 0x0001
	semNoGPFaultErrorBox              = 0x0002
	mbIconError                       = 0x10
)

type ioCounters struct {
	ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes uint64
}

type jobBasicLimitInfo struct {
	PerProcessUserTimeLimit int64
	PerJobUserTimeLimit     int64
	LimitFlags              uint32
	MinimumWorkingSetSize   uintptr
	MaximumWorkingSetSize   uintptr
	ActiveProcessLimit      uint32
	Affinity                uintptr
	PriorityClass           uint32
	SchedulingClass         uint32
}

type jobExtendedLimitInfo struct {
	Basic                 jobBasicLimitInfo
	Io                    ioCounters
	ProcessMemoryLimit    uintptr
	JobMemoryLimit        uintptr
	PeakProcessMemoryUsed uintptr
	PeakJobMemoryUsed     uintptr
}

// jobHandle holds a Job Object that kills the engine if this program ends abruptly.
var jobHandle uintptr

func platformInit() {
	// Missing DLLs or crashes of the engine should not pop up system dialogs; we report them ourselves.
	procSetErrorMode.Call(semFailCriticalErrors | semNoGPFaultErrorBox)
	h, _, _ := procCreateJobObjectW.Call(0, 0)
	if h == 0 {
		return
	}
	var info jobExtendedLimitInfo
	info.Basic.LimitFlags = jobObjectLimitKillOnJobClose
	r, _, _ := procSetInformationJobObject.Call(h, jobObjectExtendedLimitInformation, uintptr(unsafe.Pointer(&info)), unsafe.Sizeof(info))
	if r == 0 {
		syscall.CloseHandle(syscall.Handle(h))
		return
	}
	jobHandle = h
}

func setChildAttrs(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
}

func attachChild(cmd *exec.Cmd) {
	if jobHandle == 0 || cmd.Process == nil {
		return
	}
	ph, err := syscall.OpenProcess(processSetQuota|processTerminate, false, uint32(cmd.Process.Pid))
	if err != nil {
		return
	}
	defer syscall.CloseHandle(ph)
	procAssignProcessToJobObject.Call(jobHandle, uintptr(ph))
}

func terminate(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = cmd.Process.Kill()
	}
}

func engineEnv(dir string) []string { return os.Environ() }

func exitMessage(code int, err error) string {
	switch uint32(code) {
	case 0xC0000135:
		return tr("Движку не хватает системной библиотеки Windows (обычно это Microsoft Visual C++ Redistributable). Установите её с сайта Microsoft (https://aka.ms/vs/17/release/vc_redist.x64.exe) и нажмите «Повторить».")
	case 0xC000001D:
		return tr("Процессор не поддерживает инструкции, нужные этой сборке движка.")
	case 0xC0000005:
		return tr("Движок аварийно завершился (ошибка доступа к памяти). Подробности — в журнале ниже.")
	}
	return fmt.Sprintf(tr("Движок неожиданно завершился (код %d). Подробности — в журнале ниже."), code)
}

// openWindow opens the program's window: an Edge or Chrome window without tabs and address bar (maximized, if asked)
// or, with tab (launch_mode "tab") or when neither is installed, a tab of the default browser.
func openWindow(u string, tab, maximized bool) error {
	if tab {
		return exec.Command("rundll32", "url.dll,FileProtocolHandler", u).Start()
	}
	var cands []string
	for _, env := range []string{"ProgramFiles(x86)", "ProgramFiles", "LocalAppData"} {
		if base := os.Getenv(env); base != "" {
			cands = append(cands, filepath.Join(base, `Microsoft\Edge\Application\msedge.exe`))
		}
	}
	for _, env := range []string{"ProgramFiles", "ProgramFiles(x86)", "LocalAppData"} {
		if base := os.Getenv(env); base != "" {
			cands = append(cands, filepath.Join(base, `Google\Chrome\Application\chrome.exe`))
		}
	}
	for _, c := range cands {
		if _, err := os.Stat(c); err == nil {
			cmd := exec.Command(c, appWindowArgs(u, maximized)...)
			if err := cmd.Start(); err == nil {
				_ = cmd.Process.Release()
				return nil
			}
		}
	}
	return exec.Command("rundll32", "url.dll,FileProtocolHandler", u).Start()
}

func openFolder(p string) error { return exec.Command("explorer", p).Start() }

// The own window (window.go): the program ttranslator-window.exe next to Ttranslator.exe. Its icon is its own
// resource; WebView2 keeps its data in the folder given by --data.
const windowHelperName = "ttranslator-window.exe"

func windowArgs(data string) []string { return nil }

// windowChildAttrs: a window program, started as it is (the hidden-window flags of setChildAttrs would hide it).
func windowChildAttrs(cmd *exec.Cmd) {}

func fatal(msg string) {
	if logger != nil {
		logger.Print(msg)
	}
	t, _ := syscall.UTF16PtrFromString(msg)
	c, _ := syscall.UTF16PtrFromString("Ttranslator")
	procMessageBoxW.Call(0, uintptr(unsafe.Pointer(t)), uintptr(unsafe.Pointer(c)), mbIconError)
	os.Exit(1)
}

func regString(path, name string) string {
	var k syscall.Handle
	p, _ := syscall.UTF16PtrFromString(path)
	if syscall.RegOpenKeyEx(syscall.HKEY_LOCAL_MACHINE, p, 0, syscall.KEY_READ, &k) != nil {
		return ""
	}
	defer syscall.RegCloseKey(k)
	n16, _ := syscall.UTF16PtrFromString(name)
	buf := make([]uint16, 512)
	n := uint32(len(buf) * 2)
	var typ uint32
	if syscall.RegQueryValueEx(k, n16, nil, &typ, (*byte)(unsafe.Pointer(&buf[0])), &n) != nil {
		return ""
	}
	return strings.TrimSpace(syscall.UTF16ToString(buf))
}

func machineInfo() Machine {
	m := Machine{Threads: runtime.NumCPU()}
	m.CPU = regString(`HARDWARE\DESCRIPTION\System\CentralProcessor\0`, "ProcessorNameString")
	type memStatusEx struct {
		Length, MemoryLoad                                                                     uint32
		TotalPhys, AvailPhys, TotalPageFile, AvailPageFile, TotalVirtual, AvailVirtual, AvailX uint64
	}
	ms := memStatusEx{}
	ms.Length = uint32(unsafe.Sizeof(ms))
	if r, _, _ := procGlobalMemoryStatusEx.Call(uintptr(unsafe.Pointer(&ms))); r != 0 {
		m.RamGB = math.Round(float64(ms.TotalPhys)/(1<<30)*10) / 10
	}
	cv := `SOFTWARE\Microsoft\Windows NT\CurrentVersion`
	build, _ := strconv.Atoi(regString(cv, "CurrentBuildNumber"))
	name := "Windows 10"
	if build >= 22000 {
		name = "Windows 11"
	}
	if dv := regString(cv, "DisplayVersion"); dv != "" {
		name += " " + dv
	}
	if build > 0 {
		name += fmt.Sprintf(tr(" (сборка %d)"), build)
	}
	m.OS = name
	return m
}
