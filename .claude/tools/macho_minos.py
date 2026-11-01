# Minimum macOS version (and SDK) of every Mach-O file under the given folders, read from the load commands
# (LC_BUILD_VERSION or LC_VERSION_MIN_MACOSX); universal files are shown per slice. Works on Linux, no modules needed.
#   python3 -I .claude/tools/macho_minos.py <folder> [<folder>...] [--libs]
# --libs: also the libraries that llama-server and sherpa-onnx-offline-tts link to.
import os
import struct
import sys

LC_BUILD_VERSION, LC_VERSION_MIN_MACOSX, LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB = 0x32, 0x24, 0xC, 0x80000018
CPU = {0x01000007: 'x86_64', 0x0100000C: 'arm64'}


def ver(v):
    return f"{v >> 16}.{(v >> 8) & 0xff}.{v & 0xff}"


def thin(data, off):
    if struct.unpack_from('<I', data, off)[0] != 0xFEEDFACF:
        return None
    cpu, _, _, ncmds, _, _, _ = struct.unpack_from('<IIIIIII', data, off + 4)
    p, res = off + 32, {'arch': CPU.get(cpu, hex(cpu)), 'minos': None, 'sdk': None, 'libs': []}
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II', data, p)
        if cmd == LC_BUILD_VERSION:
            _, minos, sdk = struct.unpack_from('<III', data, p + 8)
            res['minos'], res['sdk'] = ver(minos), ver(sdk)
        elif cmd == LC_VERSION_MIN_MACOSX:
            minos, sdk = struct.unpack_from('<II', data, p + 8)
            res['minos'], res['sdk'] = ver(minos), ver(sdk)
        elif cmd in (LC_LOAD_DYLIB, LC_LOAD_WEAK_DYLIB):
            name_off = struct.unpack_from('<I', data, p + 8)[0]
            name = data[p + name_off:p + size].split(b'\0')[0].decode()
            res['libs'].append(name + (' (weak)' if cmd == LC_LOAD_WEAK_DYLIB else ''))
        p += size
    return res


def slices(path):
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 8:
        return []
    magic = struct.unpack_from('>I', data, 0)[0]
    if magic in (0xCAFEBABE, 0xCAFEBABF):  # universal file: one slice per architecture
        out = []
        for i in range(struct.unpack_from('>I', data, 4)[0]):
            if magic == 0xCAFEBABE:
                off = struct.unpack_from('>IIIII', data, 8 + i * 20)[2]
            else:
                off = struct.unpack_from('>IIQQII', data, 8 + i * 32)[2]
            r = thin(data, off)
            if r:
                out.append(r)
        return out
    r = thin(data, 0)
    return [r] if r else []


def main():
    show_libs = '--libs' in sys.argv
    for root in [a for a in sys.argv[1:] if not a.startswith('--')]:
        seen = {}
        for dirpath, _, files in os.walk(root):
            for name in sorted(files):
                path = os.path.join(dirpath, name)
                if os.path.islink(path):
                    continue
                for r in slices(path):
                    seen.setdefault((r['arch'], r['minos'], r['sdk']), []).append(os.path.relpath(path, root))
                    if show_libs and name in ('llama-server', 'sherpa-onnx-offline-tts'):
                        print(f"  {name} [{r['arch']}] links: " + ', '.join(r['libs']))
        print(f"== {root}")
        for (arch, minos, sdk), names in sorted(seen.items(), key=lambda kv: str(kv[0])):
            more = f' … (+{len(names) - 4})' if len(names) > 4 else ''
            print(f"  {arch}: minos {minos}, sdk {sdk} — {len(names)} files: {', '.join(names[:4])}{more}")


if __name__ == '__main__':
    main()
