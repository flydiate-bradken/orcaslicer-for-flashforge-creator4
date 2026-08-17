#!/usr/bin/env python3
"""
Raw TCP client for FlashForge's legacy control protocol (port 8899).

STATUS: CONFIRMED against a real Creator 4 (Creator4S, firmware V1.0.0) for
login/logout, all five read-only queries (info/temp/status/progress/
position), set-temp, set-bed-temp, and led-on/led-off -- see
PROTOCOL_NOTES.md "Confirmed from a real session" and "Commands" for
details (raw response text for the write commands hasn't been captured
verbatim yet, unlike the reads). pause/resume/stop are still unconfirmed:
the printer was idle during every session tried so far, so there's been
nothing to pause/resume/stop against.

Stdlib only, no dependencies.

Usage:
    python ff_control.py <printer-ip> info
    python ff_control.py <printer-ip> temp
    python ff_control.py <printer-ip> status
    python ff_control.py <printer-ip> progress
    python ff_control.py <printer-ip> position
    python ff_control.py <printer-ip> pause --confirm
    python ff_control.py <printer-ip> resume --confirm
    python ff_control.py <printer-ip> stop --confirm
    python ff_control.py <printer-ip> set-temp --tool 0 --celsius 220 --confirm
    python ff_control.py <printer-ip> set-bed-temp --celsius 60 --confirm
    python ff_control.py <printer-ip> led-on --confirm
    python ff_control.py <printer-ip> led-on --r 0 --g 0 --b 255 --confirm
    python ff_control.py <printer-ip> led-off --confirm

See PROTOCOL_NOTES.md for the command reference and sources, and
control/README.md for how to use this against the real machine safely.
"""

import argparse
import socket
import sys

DEFAULT_PORT = 8899
DEFAULT_TIMEOUT = 5.0
QUIET_WINDOW = 0.3  # seconds of silence taken to mean "response finished" -- see PROTOCOL_NOTES.md

# Sanity clamps for set-temp/set-bed-temp -- not the printer's real limits
# (those aren't documented anywhere checked), just a guard against typos
# turning into "S9999" sent straight to a heater. Nozzle range covers the
# ABS profile already confirmed elsewhere in this repo (230-235C) with
# headroom; bed range covers the confirmed 110C ABS bed temp with headroom.
NOZZLE_TEMP_RANGE = (0, 280)
BED_TEMP_RANGE = (0, 130)


class FlashForgeControlClient:
    """
    Client for FlashForge's legacy text control protocol.

    Confirmed against a real Creator 4 for login/logout, all read-only
    queries, set-temp/set-bed-temp, and led-on/led-off -- see module
    docstring and PROTOCOL_NOTES.md. Pause/resume/stop are implemented but
    still unconfirmed.
    """

    def __init__(self, host: str, port: int = DEFAULT_PORT, timeout: float = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def _send(self, command: str) -> str:
        """Send one command and return the raw response text."""
        if self.sock is None:
            raise RuntimeError("not connected -- call connect() first")
        self.sock.sendall(f"~{command}\n".encode("ascii"))
        return self._read_response()

    def _read_response(self, quiet_window: float = QUIET_WINDOW) -> str:
        """
        Read until the socket goes quiet for `quiet_window` seconds.

        Not a confirmed part of the protocol -- see PROTOCOL_NOTES.md
        "Framing". No source documents a reliable end-of-response marker,
        so this is a pragmatic stand-in until a real capture shows better.
        """
        assert self.sock is not None
        self.sock.settimeout(quiet_window)
        chunks = []
        while True:
            try:
                chunk = self.sock.recv(4096)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
        self.sock.settimeout(self.timeout)
        return b"".join(chunks).decode("ascii", errors="replace")

    # -- session --
    def login(self) -> str:
        return self._send("M601 S1")

    def logout(self) -> str:
        return self._send("M602")

    # -- read-only queries --
    def get_info(self) -> str:
        return self._send("M115")

    def get_temp(self) -> str:
        return self._send("M105")

    def get_endstop_status(self) -> str:
        return self._send("M119")

    def get_progress(self) -> str:
        return self._send("M27")

    def get_position(self) -> str:
        return self._send("M114")

    # -- print control (acts on a real, possibly mid-print machine) --
    def pause(self) -> str:
        return self._send("M25")

    def resume(self) -> str:
        return self._send("M24")

    def stop(self) -> str:
        return self._send("M26")

    # -- temperature control (acts on the real heaters, immediately) --
    def set_temp(self, tool: int, celsius: float) -> str:
        """M104 -- async, doesn't wait for the target to be reached. tool: 0=right/T0, 1=left/T1."""
        return self._send(f"M104 S{celsius:g} T{tool}")

    def set_bed_temp(self, celsius: float) -> str:
        """M140 -- async, doesn't wait for the target to be reached."""
        return self._send(f"M140 S{celsius:g}")

    # -- LED (cosmetic, essentially no downside even if the protocol is wrong here) --
    def led_on(self, r: int = 255, g: int = 255, b: int = 255) -> str:
        return self._send(f"M146 r{r} g{g} b{b} F0")

    def led_off(self) -> str:
        return self._send("M146 r0 g0 b0 F0")


# name -> (client method, needs --confirm)
ACTIONS = {
    "info": (FlashForgeControlClient.get_info, False),
    "temp": (FlashForgeControlClient.get_temp, False),
    "status": (FlashForgeControlClient.get_endstop_status, False),
    "progress": (FlashForgeControlClient.get_progress, False),
    "position": (FlashForgeControlClient.get_position, False),
    "pause": (FlashForgeControlClient.pause, True),
    "resume": (FlashForgeControlClient.resume, True),
    "stop": (FlashForgeControlClient.stop, True),
    "led-off": (FlashForgeControlClient.led_off, True),
}

TEMP_COMMANDS = ("set-temp", "set-bed-temp")
LED_ON_COMMAND = "led-on"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("host", help="printer IP, e.g. 172.16.128.123")
    parser.add_argument("command", choices=sorted(ACTIONS) + list(TEMP_COMMANDS) + [LED_ON_COMMAND])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="required for any command that changes what the printer is doing",
    )
    parser.add_argument("--celsius", type=float, default=None, help="target temperature for set-temp/set-bed-temp")
    parser.add_argument(
        "--tool", type=int, choices=[0, 1], default=0, help="tool index for set-temp: 0=right/T0, 1=left/T1"
    )
    parser.add_argument("--r", type=int, default=255, help="LED red 0-255 (led-on only)")
    parser.add_argument("--g", type=int, default=255, help="LED green 0-255 (led-on only)")
    parser.add_argument("--b", type=int, default=255, help="LED blue 0-255 (led-on only)")
    args = parser.parse_args()

    if args.command in TEMP_COMMANDS:
        if not args.confirm:
            parser.error(f"'{args.command}' changes what the printer is doing -- rerun with --confirm")
        if args.celsius is None:
            parser.error(f"'{args.command}' requires --celsius")
        lo, hi = NOZZLE_TEMP_RANGE if args.command == "set-temp" else BED_TEMP_RANGE
        if not (lo <= args.celsius <= hi):
            parser.error(f"--celsius {args.celsius} outside sane range {lo}-{hi}")
        if args.command == "set-temp":
            action = lambda c: c.set_temp(args.tool, args.celsius)  # noqa: E731
        else:
            action = lambda c: c.set_bed_temp(args.celsius)  # noqa: E731
    elif args.command == LED_ON_COMMAND:
        if not args.confirm:
            parser.error(f"'{args.command}' changes what the printer is doing -- rerun with --confirm")
        for name, val in (("r", args.r), ("g", args.g), ("b", args.b)):
            if not (0 <= val <= 255):
                parser.error(f"--{name} {val} outside 0-255")
        action = lambda c: c.led_on(args.r, args.g, args.b)  # noqa: E731
    else:
        method, needs_confirm = ACTIONS[args.command]
        if needs_confirm and not args.confirm:
            parser.error(f"'{args.command}' changes what the printer is doing -- rerun with --confirm")
        action = method

    client = FlashForgeControlClient(args.host, args.port)
    print(f"connecting to {args.host}:{args.port} ...")
    try:
        client.connect()
    except OSError as e:
        print(f"FAILED to connect: {e}", file=sys.stderr)
        print(
            "If this is a connection refused/timeout, the Creator 4 likely isn't "
            "listening on the legacy port 8899 -- see PROTOCOL_NOTES.md for the "
            "newer JSON API on port 8898 as the next thing to try.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        print("login:", client.login().strip() or "(empty response)")
        print(f"\n{args.command}:")
        print(action(client).strip() or "(empty response)")
    finally:
        print("\nlogout:", client.logout().strip() or "(empty response)")
        client.close()


if __name__ == "__main__":
    main()
