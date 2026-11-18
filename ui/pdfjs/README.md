# PDF.js in Ttranslator

PDF.js (Mozilla, Apache-2.0) reads PDF files inside the window: the text of pages that have it, and the pages of
scans as pictures for the model to read (the author's consent: 18.11.2026). The page loads it only when a PDF is
opened (`import('/pdfjs/pdf.min.mjs')`); nothing is fetched from the network.

Source: the npm package `pdfjs-dist` 6.5.438 (published by Mozilla, 01.11.2026), the "legacy" build — it works in
older browser engines too (WebKitGTK on Linux, macOS 13.3+, Android WebView):
`https://registry.npmjs.org/pdfjs-dist/-/pdfjs-dist-6.5.438.tgz`, SHA-256
`7461aefcd27c4ef0dd76f9ca5760f09466eb6b3f934432670c12132e7b3d6faa`. The same version is the GitHub release
`v6.5.438` of mozilla/pdf.js (the release archive has the same files, not minified).

| File here | From the package | SHA-256 |
|---|---|---|
| `pdf.min.mjs` | `legacy/build/pdf.min.mjs` | `522ad2c83bc8a0010e7f0cc60d0892b77c8d2bf2c9702dc12288311d94270f42` |
| `pdf.worker.min.mjs` | `legacy/build/pdf.worker.min.mjs` | `b4c8353ded0d88d2e2009574a29eb4e0c3ff7e942ecdf51ef5f71566a9667f31` |
| `wasm/jbig2.wasm` | `wasm/jbig2.wasm` — black-and-white scans (JBIG2), from PDFium (BSD-3-Clause) | `466f45c2a61a698152fb5400c27e56ff2ceb73dcb71fde3fc366a502308eaab0` |
| `wasm/openjpeg.wasm` | `wasm/openjpeg.wasm` — JPEG 2000 pictures, OpenJPEG (BSD-2-Clause) | `7ea4b2b04613370ad4e9c1162da750cc88b4b176eac0d0c164b3caff23fc0a46` |
| `wasm/qcms_bg.wasm` | `wasm/qcms_bg.wasm` — colour profiles, qcms (MIT) | `663d86126d5f5fcb1c61490f94353e2a8375660b8c5498ab3ebab5a34b08800e` |
| `LICENSE`, `wasm/LICENSE_*` | the licences of PDF.js and of the three decoders | |

Not taken: the viewer (`web/`), source maps, the scripting sandbox (QuickJS), fonts and CMaps (pictures of scans
need none; text of most PDFs is read without them — CJK text PDFs with predefined CMaps may need `cmaps/` later).

To update: take the same files of a newer `pdfjs-dist`, write the new version and hashes here, in
`THIRD-PARTY.txt` and in «О программе», and run the tests (`e2e_files.py` reads a text PDF and a scanned one).
