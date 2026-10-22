# The program's icon in Ttranslator.exe: the Windows build carries the icon resource (RT_GROUP_ICON with the
# images 16…256 px), the same as Ttranslator.ico; and both are up to date with the drawing LOGO in ui/index.html
# (make_icon.go run again on the current page gives the same files).
# Usage: icon_check.py <Ttranslator.exe> <source/launcher> <ui/index.html> <work dir>
import sys, os, io, struct, shutil, subprocess
import pefile
from PIL import Image
EXE, LAUNCHER, PAGE, W = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)

pe = pefile.PE(EXE)
icons, group = {}, None
for t in (pe.DIRECTORY_ENTRY_RESOURCE.entries if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE') else []):
    for e in t.directory.entries:
        for l in e.directory.entries:
            data = pe.get_data(l.data.struct.OffsetToData, l.data.struct.Size)
            if t.id == 3: icons[e.id] = data
            if t.id == 14 and group is None: group = data
ok(group is not None and len(icons) >= 8, 'Ttranslator.exe has an icon resource: %d images' % len(icons))
ico = b''
if group:
    n = struct.unpack_from('<HHH', group)[2]
    out = io.BytesIO(); out.write(struct.pack('<HHH', 0, 1, n)); off = 6 + 16 * n; blobs = []
    for i in range(n):
        w, h, cc, r, planes, bits, size, nid = struct.unpack_from('<BBBBHHIH', group, 6 + 14 * i)
        out.write(struct.pack('<BBBBHHII', w, h, cc, r, planes, bits, size, off)); off += size; blobs.append(icons[nid])
    for x in blobs: out.write(x)
    ico = out.getvalue()
ref = open(os.path.join(LAUNCHER, 'Ttranslator.ico'), 'rb').read()
ok(ico == ref, 'the icon in the exe is Ttranslator.ico')
im = Image.open(io.BytesIO(ref))
ok(sorted(im.info.get('sizes', [])) == [(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 256)], 'sizes: %s' % sorted(im.info.get('sizes', [])))
im.size = (32, 32); px = im.convert('RGBA')
cols = {px.getpixel((x, y))[:3] for x in range(32) for y in range(32) if px.getpixel((x, y))[3] == 255}
ok((117, 5, 117) in cols and (255, 255, 255) in cols, 'purple T with a white outline')

# up to date with the drawing: run the generator on a copy of the current page and compare
tmp = os.path.join(W, 'icon-check'); shutil.rmtree(tmp, ignore_errors=True)
os.makedirs(os.path.join(tmp, 'source', 'launcher')); os.makedirs(os.path.join(tmp, 'ui'))
shutil.copy(os.path.join(LAUNCHER, 'make_icon.go'), os.path.join(tmp, 'source', 'launcher'))
shutil.copy(PAGE, os.path.join(tmp, 'ui', 'index.html'))
r = subprocess.run(['go', 'run', 'make_icon.go'], cwd=os.path.join(tmp, 'source', 'launcher'), capture_output=True, text=True)
same = r.returncode == 0 and all(open(os.path.join(tmp, 'source', 'launcher', f), 'rb').read() == open(os.path.join(LAUNCHER, f), 'rb').read()
                                 for f in ('Ttranslator.ico', 'rsrc_windows_amd64.syso'))
ok(same, 'Ttranslator.ico and rsrc_windows_amd64.syso match the drawing LOGO in ui/index.html (go run make_icon.go) %s' % (r.stderr.strip()[:200]))
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
