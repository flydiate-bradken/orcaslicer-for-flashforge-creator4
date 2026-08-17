"""
Minimal mock of FlashForge's legacy control protocol (port 8899), for
testing ff_control.py's request framing / response parsing without real
hardware.

Canned responses for M601/M602/M115/M105/M119/M27/M114 are **verbatim from
a real Creator 4** (`Creator4S`, firmware V1.0.0), captured 2026-08-17 via
ff_control.py while idle -- see ../PROTOCOL_NOTES.md "Confirmed from a real
session". M25/M24/M26 (pause/resume/stop) are still unconfirmed guesses,
since there was no active print to test those against; they're synthesized
here only to exercise ff_control.py's parsing, not because they're known
to be real. See ../captures/README.md for how pause/resume/stop could get
confirmed too.
"""

import socketserver
import threading

# Keyed on the exact command text sent after the '~' prefix is stripped.
RESPONSES = {
    "M601 S1": "CMD M601 Received.\r\nControl Success V2.1.\r\nok\r\n",
    "M602": "CMD M602 Received.\r\nControl Release.\r\nok\r\n",
    "M115": (
        "CMD M115 Received.\r\n"
        "Machine Type: FlashForge Creator 4\r\n"
        "Machine Name: Creator4S\r\n"
        "Firmware: V1.0.0\r\n"
        "SN: SNMOIC9400003\r\n"
        "X: 400 Y: 350 Z: 500\r\n"
        "Tool Count:2\r\n"
        "Mac Address:94A408B472BE \r\n"
        "ok\r\n"
    ),
    "M105": "CMD M105 Received.\r\nT0:21/0 T1:20/0 B:20/0\r\nok\r\n",
    "M119": (
        "CMD M119 Received.\r\n"
        "Endstop: X-max: 400 Y-max: 350 Z-min: 0\r\n"
        "Status: S:1 L:0 J:0 F:0\r\n"
        "MachineStatus: READY\r\n"
        "MoveMode: READY\r\n"
        "CurrentFile:\r\n"
        "LED:1\r\n"
        "ok\r\n"
    ),
    "M27": "CMD M27 Received.\r\nSD printing byte 0/1000\r\nok\r\n",
    "M114": "CMD M114 Received.\r\nX1:-230 X2:230 Y:175 Z:0 A:5 B:0\r\nok\r\n",
    # Unconfirmed -- see docstring above.
    "M25": "CMD M25 Received.\r\nok\r\n",
    "M24": "CMD M24 Received.\r\nok\r\n",
    "M26": "CMD M26 Received.\r\nok\r\n",
    # Also unconfirmed. Keyed on the exact strings ff_control.py's smoke test
    # sends -- see run_control_smoke_test.py.
    "M104 S220 T0": "CMD M104 Received.\r\nok\r\n",
    "M140 S60": "CMD M140 Received.\r\nok\r\n",
    "M146 r255 g255 b255 F0": "CMD M146 Received.\r\nok\r\n",
    "M146 r0 g0 b0 F0": "CMD M146 Received.\r\nok\r\n",
}


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        while True:
            buf = b""
            while not buf.endswith(b"\n"):
                chunk = self.request.recv(4096)
                if not chunk:
                    return
                buf += chunk
            line = buf.decode("ascii", errors="ignore").strip()
            if not line.startswith("~"):
                self.request.sendall(b"CMD ? Received.\r\nUnrecognized command\r\nok\r\n")
                continue
            cmd = line[1:]
            resp = RESPONSES.get(cmd, f"CMD {cmd.split(' ')[0]} Received.\r\nok\r\n")
            self.request.sendall(resp.encode("ascii"))


class MockPrinterServer:
    """Threaded TCP server on 127.0.0.1:<random free port> speaking the mock protocol."""

    def __init__(self) -> None:
        self._server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), _Handler)
        self._server.daemon_threads = True
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
