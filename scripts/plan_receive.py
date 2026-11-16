"""Local receiver for a plan re-read: saves the read-only workflow JSON that scripts/plan_read_chrome.js posts from
the GHL tab. Listens on 127.0.0.1 only, accepts one POST from app.gohighlevel.com, then exits.
Usage: python3 -I scripts/plan_receive.py data/raw/<YYYY-MM-DD>_plan-read.json"""
import http.server, sys

OUT = sys.argv[1]


class H(http.server.BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "https://app.gohighlevel.com")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def do_OPTIONS(self):
        self.send_response(204); self.cors(); self.end_headers()

    def do_POST(self):
        n = int(self.headers["Content-Length"])
        open(OUT, "wb").write(self.rfile.read(n))
        self.send_response(200); self.cors(); self.end_headers(); self.wfile.write(b"ok")
        print(f"Saved {n:,} bytes to {OUT}", flush=True)
        raise SystemExit(0)

    def log_message(self, *a):
        pass


try:
    http.server.HTTPServer(("127.0.0.1", 8765), H).serve_forever()
except SystemExit:
    pass
