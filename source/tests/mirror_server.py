# Range-capable, throttled static file server for testing downloads.
import os, sys, time, http.server, socketserver
ROOT = sys.argv[1]; PORT = int(sys.argv[2]); RATE = float(sys.argv[3])  # bytes per second
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = os.path.join(ROOT, os.path.basename(self.path.split('?')[0]))
        if not os.path.isfile(p):
            self.send_response(404); self.end_headers(); return
        size = os.path.getsize(p); start, end = 0, size - 1
        rng = self.headers.get('Range')
        if rng and rng.startswith('bytes='):
            a, _, b = rng[6:].partition('-'); start = int(a); end = int(b) if b else size - 1
            if start >= size:
                self.send_response(416); self.end_headers(); return
            self.send_response(206); self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_response(200)
        self.send_header('Content-Length', str(end - start + 1)); self.send_header('Accept-Ranges', 'bytes'); self.end_headers()
        with open(p, 'rb') as f:
            f.seek(start); left = end - start + 1; chunk = 64 * 1024
            while left > 0:
                data = f.read(min(chunk, left))
                if not data: break
                try: self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError): return
                left -= len(data); time.sleep(len(data) / RATE)
class S(socketserver.ThreadingMixIn, http.server.HTTPServer): daemon_threads = True
S(('127.0.0.1', PORT), H).serve_forever()
