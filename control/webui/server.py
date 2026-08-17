#!/usr/bin/env python3
"""
Local browser status page for the Creator 4.

Browsers can't open raw TCP sockets, so this is a small local HTTP server
that: polls the printer over ff_control.py's TCP client (port 8899),
exposes the result as JSON at /api/status, and serves a page that polls
that endpoint and embeds the existing camera stream via <iframe>. Runs on
your machine, talks to the printer on your LAN -- nothing goes further
than that.

Stdlib only, no dependencies -- consistent with the rest of this repo.

STATUS: reads (info/temp/status/progress) are confirmed against a real
Creator 4 (see ../PROTOCOL_NOTES.md "Confirmed from a real session"). The
temperature setters (POST /api/set-temp, /api/set-bed-temp) send M104/M140
-- documented across independent sources for this protocol family but NOT
yet tried against this Creator 4 at all -- so the page's Set buttons have
a browser confirm() prompt in front of them, mirroring ff_control.py's
--confirm flag. The LED toggle (POST /api/led-on, /api/led-off) is also
unconfirmed but has no confirm prompt -- worst case a light doesn't change,
categorically lower risk than heating something. Doesn't expose
pause/resume/stop yet -- those are separately unconfirmed and not wired in
here (see ../README.md "Next steps").

Usage:
    python control/webui/server.py 172.16.128.123
    then open http://localhost:8000 in a browser

    python control/webui/server.py 172.16.128.123 --web-port 9000 \\
        --camera-url http://172.16.128.123:8080/stream_simple.html
"""

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ff_control import BED_TEMP_RANGE, NOZZLE_TEMP_RANGE, FlashForgeControlClient  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"

STATIC_FILES = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "application/javascript"),
    "/style.css": ("style.css", "text/css"),
}


def parse_temp(raw: str) -> dict:
    """
    Parse 'T0:21/0 T1:20/0 B:20/0' (confirmed real format, see
    PROTOCOL_NOTES.md) into {"T0": {"current": 21.0, "target": 0.0}, ...}.
    Best-effort: unrecognized tokens are skipped rather than raising, since
    this feeds a live display where a partial read beats a crashed one.
    """
    result = {}
    for token in raw.split():
        if ":" not in token or "/" not in token:
            continue
        name, _, vals = token.partition(":")
        cur, _, target = vals.partition("/")
        try:
            result[name] = {"current": float(cur), "target": float(target)}
        except ValueError:
            continue
    return result


def parse_progress(raw: str) -> dict:
    """Parse 'SD printing byte X/Y' into current/total/percent."""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith("SD printing byte"):
            nums = line[len("SD printing byte"):].strip()
            cur_s, _, total_s = nums.partition("/")
            try:
                cur, total = int(cur_s), int(total_s)
            except ValueError:
                break
            percent = round(100 * cur / total, 1) if total else 0.0
            return {"current": cur, "total": total, "percent": percent}
    return {"current": None, "total": None, "percent": None}


def parse_kv_block(raw: str) -> dict:
    """
    Best-effort parse of the loose 'Key: value' lines M115/M119 return
    into a flat dict (one entry per line that has a colon). Multi-value
    lines (Endstop:, Status:) end up as one string value rather than being
    further decomposed -- their internal structure isn't fully nailed down
    yet (see PROTOCOL_NOTES.md), and guessing wrong here would be worse
    than passing the text through as-is.
    """
    result = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line == "ok" or line.startswith("CMD"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def fetch_status(host: str, port: int, timeout: float) -> dict:
    """One login -> read everything -> logout session, per poll."""
    client = FlashForgeControlClient(host, port, timeout=timeout)
    client.connect()
    try:
        client.login()
        info_raw = client.get_info()
        temp_raw = client.get_temp()
        status_raw = client.get_endstop_status()
        progress_raw = client.get_progress()
        position_raw = client.get_position()
    finally:
        try:
            client.logout()
        except OSError:
            pass  # best-effort -- we're closing the socket right after anyway
        client.close()

    return {
        "ok": True,
        "timestamp": time.time(),
        "info": parse_kv_block(info_raw),
        "temp": parse_temp(temp_raw),
        "status": parse_kv_block(status_raw),
        "progress": parse_progress(progress_raw),
        # Not parsed -- X1/X2/Y/Z/A/B dual-toolhead format, see PROTOCOL_NOTES.md.
        "position_raw": position_raw.strip(),
    }


def send_write_command(host: str, port: int, timeout: float, fn) -> dict:
    """
    Open a session, run one write command (fn(client) -> raw response
    string), log out, close. Same one-command-per-session shape as
    fetch_status, just for a single action instead of five reads.
    """
    client = FlashForgeControlClient(host, port, timeout=timeout)
    client.connect()
    try:
        client.login()
        response = fn(client)
    finally:
        try:
            client.logout()
        except OSError:
            pass
        client.close()
    return {"ok": True, "timestamp": time.time(), "response": response.strip()}


class Handler(BaseHTTPRequestHandler):
    # set by main() before the server starts
    printer_host: str = ""
    printer_port: int = 8899
    control_timeout: float = 5.0
    camera_url: str = ""

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def do_GET(self) -> None:
        if self.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[self.path]
            self._serve_static(filename, content_type)
        elif self.path == "/api/status":
            self._serve_status()
        elif self.path == "/api/config":
            self._send_json({"camera_url": self.camera_url})
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        if self.path == "/api/set-temp":
            self._handle_set_temp()
        elif self.path == "/api/set-bed-temp":
            self._handle_set_bed_temp()
        elif self.path == "/api/led-on":
            self._run_write(lambda c: c.led_on())
        elif self.path == "/api/led-off":
            self._run_write(lambda c: c.led_off())
        else:
            self.send_error(404)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    def _handle_set_temp(self) -> None:
        try:
            body = self._read_json_body()
            tool = int(body["tool"])
            celsius = float(body["celsius"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "expected JSON body {tool: 0|1, celsius: number}"}, status=400)
            return
        if tool not in (0, 1):
            self._send_json({"ok": False, "error": "tool must be 0 (right/T0) or 1 (left/T1)"}, status=400)
            return
        lo, hi = NOZZLE_TEMP_RANGE
        if not (lo <= celsius <= hi):
            self._send_json({"ok": False, "error": f"celsius {celsius} outside sane range {lo}-{hi}"}, status=400)
            return
        self._run_write(lambda c: c.set_temp(tool, celsius))

    def _handle_set_bed_temp(self) -> None:
        try:
            body = self._read_json_body()
            celsius = float(body["celsius"])
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            self._send_json({"ok": False, "error": "expected JSON body {celsius: number}"}, status=400)
            return
        lo, hi = BED_TEMP_RANGE
        if not (lo <= celsius <= hi):
            self._send_json({"ok": False, "error": f"celsius {celsius} outside sane range {lo}-{hi}"}, status=400)
            return
        self._run_write(lambda c: c.set_bed_temp(celsius))

    def _run_write(self, fn) -> None:
        try:
            result = send_write_command(self.printer_host, self.printer_port, self.control_timeout, fn)
        except OSError as e:
            result = {"ok": False, "error": str(e), "timestamp": time.time()}
        self._send_json(result)

    def _serve_static(self, filename: str, content_type: str) -> None:
        try:
            data = (STATIC_DIR / filename).read_bytes()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self) -> None:
        try:
            status = fetch_status(self.printer_host, self.printer_port, self.control_timeout)
        except OSError as e:
            status = {"ok": False, "error": str(e), "timestamp": time.time()}
        self._send_json(status)

    def _send_json(self, obj: dict, status: int = 200) -> None:
        data = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("printer_host", help="Creator 4 IP, e.g. 172.16.128.123")
    parser.add_argument("--control-port", type=int, default=8899)
    parser.add_argument("--control-timeout", type=float, default=5.0)
    parser.add_argument(
        "--camera-url",
        default=None,
        help="default: http://<printer_host>:8080/stream_simple.html",
    )
    parser.add_argument("--web-port", type=int, default=8000)
    args = parser.parse_args()

    Handler.printer_host = args.printer_host
    Handler.printer_port = args.control_port
    Handler.control_timeout = args.control_timeout
    Handler.camera_url = args.camera_url or f"http://{args.printer_host}:8080/stream_simple.html"

    server = ThreadingHTTPServer(("127.0.0.1", args.web_port), Handler)
    print(f"Creator 4 status page: http://localhost:{args.web_port}")
    print(f"  printer control: {Handler.printer_host}:{Handler.printer_port}")
    print(f"  camera:          {Handler.camera_url}")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
