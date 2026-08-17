"""
Smoke test for ff_control.py against the mock printer server.

Proves the client's request framing and response parsing round-trip
correctly against a server that echoes real captured Creator 4 responses
for the confirmed commands (see ../PROTOCOL_NOTES.md "Confirmed from a
real session") and best-guess responses for the still-unconfirmed
pause/resume/stop. This is a regression check against known-good behavior,
not a substitute for testing against the real printer.

Usage: python run_control_smoke_test.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ff_control import FlashForgeControlClient  # noqa: E402
from mock_printer_server import MockPrinterServer  # noqa: E402


def main() -> None:
    server = MockPrinterServer()
    server.start()
    try:
        client = FlashForgeControlClient("127.0.0.1", server.port, timeout=2.0)
        client.connect()

        login = client.login()
        assert "Control Success" in login, f"unexpected login response: {login!r}"

        info = client.get_info()
        assert "Creator 4" in info, f"unexpected info response: {info!r}"
        assert "SNMOIC9400003" in info, f"unexpected info response: {info!r}"

        temp = client.get_temp()
        assert "T0:21/0" in temp, f"unexpected temp response: {temp!r}"

        status = client.get_endstop_status()
        assert "READY" in status, f"unexpected status response: {status!r}"
        assert "CurrentFile:" in status, f"unexpected status response: {status!r}"

        progress = client.get_progress()
        assert "SD printing byte" in progress, f"unexpected progress response: {progress!r}"

        position = client.get_position()
        assert "X1:-230" in position, f"unexpected position response: {position!r}"

        pause = client.pause()
        assert "M25" in pause, f"unexpected pause response: {pause!r}"

        resume = client.resume()
        assert "M24" in resume, f"unexpected resume response: {resume!r}"

        stop = client.stop()
        assert "M26" in stop, f"unexpected stop response: {stop!r}"

        set_temp = client.set_temp(0, 220)
        assert "M104" in set_temp, f"unexpected set_temp response: {set_temp!r}"

        set_bed_temp = client.set_bed_temp(60)
        assert "M140" in set_bed_temp, f"unexpected set_bed_temp response: {set_bed_temp!r}"

        led_on = client.led_on()
        assert "M146" in led_on, f"unexpected led_on response: {led_on!r}"

        led_off = client.led_off()
        assert "M146" in led_off, f"unexpected led_off response: {led_off!r}"

        logout = client.logout()
        assert "Control Release" in logout, f"unexpected logout response: {logout!r}"

        client.close()
        print("OK: ff_control.py client round-trips correctly against the mock server")
        print("(this says nothing about whether a real Creator 4 behaves this way -- see ../captures/README.md)")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
