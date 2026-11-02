//go:build !darwin

package main

import "os"

// programDirs (Windows, Linux): everything is in the program folder — the folder of the program file, or TDOC_ROOT —
// the data (root), the interface (res/ui) and the window program (bin).
func programDirs(exeDir string) (root, res, bin string) {
	root = exeDir
	if env := os.Getenv("TDOC_ROOT"); env != "" {
		root = env
	}
	return root, root, root
}
