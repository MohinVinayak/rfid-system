"""
Local Python HTTP Server for Chipless RFID Decoder
All CST signal processing runs in Python (scipy).
Quantity state is persisted to inventory_state.json.
"""

import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from rfid_decoder import decode_rfid, parse_cst, INVENTORY

from socketserver import ThreadingMixIn

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "inventory_state.json")

# ── QUANTITY STATE ────────────────────────────────────────────────────────────
# Loaded from disk on startup; each key is the 5-bit code, value is qty integer.

def _load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    # First run: default every item to 50 units
    return {item["code"]: 50 for item in INVENTORY}

def _save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

QTY = _load_state()

# ── SERVER ────────────────────────────────────────────────────────────────────

class RFIDHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # silence all access logs

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path, content_type="text/html"):
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path
        query  = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._send_file(os.path.join(BASE_DIR, "index.html"), "text/html")
            return

        # Manual 5-bit code lookup (includes current qty)
        if path == "/api/lookup":
            code = query.get("code", ["00000"])[0]
            try:
                dec  = int(code, 2)
                item = INVENTORY[dec] if 0 <= dec < len(INVENTORY) else None
                qty  = QTY.get(code, 0)
                self._send_json({"success": True, "code": code,
                                 "decimal": dec, "item": item, "qty": qty})
            except Exception:
                self._send_json({"success": False, "error": "Invalid binary code"}, 400)
            return

        # Full inventory list with current quantities
        if path == "/api/inventory":
            rows = []
            for it in INVENTORY:
                rows.append({**it, "qty": QTY.get(it["code"], 0)})
            self._send_json({"inventory": rows})
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)

        # Decode uploaded CST file
        if parsed.path == "/api/decode":
            content_len = int(self.headers.get("Content-Length", 0))
            raw_data    = self.rfile.read(content_len).decode("utf-8", errors="ignore")
            try:
                freqs, rcs = parse_cst(raw_data)
                res = decode_rfid(freqs, rcs)
                res["qty"] = QTY.get(res["code"], 0)
                # Include rounded points for high-performance SVG/Canvas graphing
                res["spectrum"] = {
                    "freqs": [round(float(f), 4) for f in freqs],
                    "rcs": [round(float(r), 2) for r in rcs]
                }
                self._send_json({"success": True, "data": res})
            except Exception as e:
                self._send_json({"success": False, "error": f"Decoding failed: {str(e)}"}, 400)
            return

        # Update quantity  { "code": "01011", "delta": 5 }   delta can be negative
        if parsed.path == "/api/qty":
            content_len = int(self.headers.get("Content-Length", 0))
            try:
                body  = json.loads(self.rfile.read(content_len).decode("utf-8"))
                code  = body["code"]
                delta = int(body["delta"])
                if not (len(code) == 5 and all(c in "01" for c in code)):
                    raise ValueError("bad code")
                new_qty = max(0, QTY.get(code, 0) + delta)
                QTY[code] = new_qty
                _save_state(QTY)
                # auto-update status label
                dec  = int(code, 2)
                item = INVENTORY[dec]
                self._send_json({
                    "success": True,
                    "code": code,
                    "qty": new_qty,
                    "item_name": item["name"],
                })
            except Exception as e:
                self._send_json({"success": False, "error": str(e)}, 400)
            return

        self.send_error(404)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

def run_server():
    server = ThreadedHTTPServer(("0.0.0.0", PORT), RFIDHandler)
    print("=" * 60)
    print(f"  RFID LOCAL BACKEND  →  http://localhost:{PORT}")
    print(f"  Quantity state file: {STATE_FILE}")
    print("=" * 60)
    server.serve_forever()

if __name__ == "__main__":
    run_server()
