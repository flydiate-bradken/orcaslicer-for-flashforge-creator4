# FlashForge legacy TCP control protocol (port 8899) -- notes

**Confirmed live against a real Creator 4** (`Creator4S`, firmware V1.0.0,
SN `SNMOIC9400003`) on 2026-08-17 for the session/login and all five
read-only queries -- see "Confirmed from a real session" below for the
actual captured responses. **Also confirmed working**: `M104`/`M140`
(set nozzle/bed temp) and `M146` (LED on/off), both via `ff_control.py`
and the `webui/` page -- user-reported, exact raw response text not
captured this round (see "Commands" table). Pause/resume/stop are still
unconfirmed (never safe to test against a real print until now, and the
session above had the printer idle, so there was nothing to pause/resume/
stop against). Treat those three as a hypothesis still.

## Why this protocol, and not the newer one

FlashForge printers speak one of two live-control protocols depending on
board generation:

| Protocol | Port | Format | Confirmed on |
|---|---|---|---|
| Legacy | 8899 | plain text, G-code/M-code | Finder, Finder 2, Adventurer 3, Adventurer 4 |
| Modern | 8898 (status/control), 8899 (also open, for compatibility) | JSON over HTTP | Adventurer 5M, 5M Pro, AD5X, Creator 5 |

The modern (5M-generation) protocol is the one Flashforge's own
Orca-Flashforge fork uses, and it's explicitly documented as **not**
covering the Creator 4 (see main `control/README.md`). The legacy protocol's
confirmed machines (Finder/Adventurer 3/4) are the *older* generation --
notably, the same generation known to expose its camera via a bare
mjpg-streamer instance at `<ip>:8080` with paths like `stream_simple.html`
or `?action=stream`, exactly what you're already using on the Creator 4.
That match is circumstantial, not proof, but it's the reason this folder
starts with the legacy protocol rather than the JSON one.

If the read-only legacy commands (see `control/README.md`) get refused or
time out, the JSON API on 8898 is the next thing to probe -- not written up
here yet since there's even less reason to assume the Creator 4 speaks it.

**Update: confirmed, this was the right guess.** The Creator 4 does listen
on 8899 and speaks this protocol -- see below.

## Confirmed from a real session

Captured 2026-08-17 via `ff_control.py` against a real Creator 4 on the
local network, idle (no print running). Raw responses, verbatim:

```
~M601 S1
CMD M601 Received.
Control Success V2.1.
ok

~M115
CMD M115 Received.
Machine Type: FlashForge Creator 4
Machine Name: Creator4S
Firmware: V1.0.0
SN: SNMOIC9400003
X: 400 Y: 350 Z: 500
Tool Count:2
Mac Address:94A408B472BE 
ok

~M105
CMD M105 Received.
T0:21/0 T1:20/0 B:20/0
ok

~M119
CMD M119 Received.
Endstop: X-max: 400 Y-max: 350 Z-min: 0
Status: S:1 L:0 J:0 F:0
MachineStatus: READY
MoveMode: READY
CurrentFile:
LED:1
ok

~M27
CMD M27 Received.
SD printing byte 0/1000
ok

~M114
CMD M114 Received.
X1:-230 X2:230 Y:175 Z:0 A:5 B:0
ok

~M602
CMD M602 Received.
Control Release.
ok
```

Corrections vs. what was originally assumed from the Finder/Adventurer docs:

- **Login response includes a version tag**: `Control Success V2.1.` not
  just `Control Success.` -- don't match on the exact string, match on
  `Control Success` as a substring (which is what `ff_control.py`'s test
  suite now does).
- **`M105` temp format** is `T0:<cur>/<target> T1:<cur>/<target> B:<cur>/<target>`,
  no space around the slash -- confirms there are two independently
  addressable tool temps (T0/T1) as expected for IDEX, plus bed (B).
- **`M119` is very different from the Finder's documented format.** The
  Creator 4's `Endstop:` line reports build-volume-looking numbers
  (`X-max: 400 Y-max: 350 Z-min: 0`) rather than the Finder's binary
  triggered/not-triggered flags, and adds two fields the Finder docs don't
  have at all: `CurrentFile:` (empty when idle -- presumably the filename
  when printing) and `LED:1` (on/off state). `MachineStatus`/`MoveMode`
  match the documented `READY` pattern.
- **`M27` format matches exactly** as documented (`SD printing byte
  X/Y`), just `0/1000` while idle.
- **`M114` is IDEX-specific and doesn't match the generic X/Y/Z/A/B format
  assumed earlier.** It reports `X1`/`X2` (the two toolhead X positions,
  independently -- `-230`/`230` at rest, consistent with two heads parked
  at opposite ends of a 400mm-wide axis) instead of a single `X`, plus
  `Y`/`Z`/`A`/`B`.
- Everything else (framing: `~` prefix, `\n` terminator, response ending in
  a bare `ok` line, the quiet-window read strategy in `ff_control.py`)
  worked exactly as assumed -- no changes needed there.

`Machine Name: Creator4S` (not `Creator 4`) is worth noting too -- `S` might
denote a specific hardware revision/variant, or just be this unit's
configured display name.

## Framing

- Commands are sent as `~<command>\n` -- leading tilde, trailing newline.
  Confirmed in multiple independent sources for M601/M602 specifically;
  assumed to hold for all other commands too.
- Responses seen in published examples end with a bare `ok` (sometimes
  `ok\r\n`). There's no confirmed length-prefix or fixed terminator
  documented anywhere I found, so `ff_control.py` reads until the socket
  goes quiet for ~300ms rather than scanning for a specific end marker.
  This is a pragmatic choice, not a confirmed part of the protocol --
  a real capture may show a better way to detect end-of-response.
- A session usually opens with `M601 S1` (take control) and closes with
  `M602` (release control); other commands are sent in between.

## Commands

| Purpose | Command | Status | Source |
|---|---|---|---|
| Login / take control | `M601 S1` | **CONFIRMED** (Creator 4, idle) -- see real response above | [ztripez/flashforgefinder-protocol](https://github.com/ztripez/flashforgefinder-protocol), [Slugger2k/FlashForgePrinterApi](https://github.com/Slugger2k/FlashForgePrinterApi) |
| Logout / release control | `M602` | **CONFIRMED** (Creator 4, idle) | same |
| Machine info (type, name, firmware, SN, build volume, tool count, MAC) | `M115` | **CONFIRMED** (Creator 4, idle) | [Slugger2k/FlashForgePrinterApi](https://github.com/Slugger2k/FlashForgePrinterApi) |
| Temperatures (T0/T1 tool + bed, current/target) | `M105` | **CONFIRMED** (Creator 4, idle -- all at ambient) | same |
| Endstop / machine status | `M119` | **CONFIRMED** (Creator 4, idle) -- format differs from the Finder docs, see corrections above | [ztripez/flashforgefinder-protocol](https://github.com/ztripez/flashforgefinder-protocol) |
| Print progress (bytes printed) | `M27` | **CONFIRMED** (Creator 4, idle -- `0/1000`) | same |
| Current position (X1/X2 dual-toolhead X, Y, Z, A, B) | `M114` | **CONFIRMED** (Creator 4, idle) -- IDEX-specific format, see corrections above | [Slugger2k/FlashForgePrinterApi](https://github.com/Slugger2k/FlashForgePrinterApi) |
| LED on (RGB) | `M146 r255 g255 b255 F0` | **CONFIRMED working** (Creator 4, via `webui/` and `ff_control.py led-on`) -- exact raw response not captured, effect observed | [ztripez/flashforgefinder-protocol](https://github.com/ztripez/flashforgefinder-protocol), [Slugger2k/FlashForgePrinterApi](https://github.com/Slugger2k/FlashForgePrinterApi) |
| LED off | `M146 r0 g0 b0 F0` | **CONFIRMED working** (Creator 4, via `webui/` and `ff_control.py led-off`) -- same | same |
| Pause print | `M25` | **not yet tried** -- printer was idle, nothing to pause; still just inferred from standard 3D-printer M-code conventions, not directly confirmed in either source above | inferred |
| Resume print | `M24` | **not yet tried**, same caveat | inferred |
| Stop print | `M26` | **not yet tried**, same caveat | listed as `PRINT_STOP` in Slugger2k's table |
| Start print from file | `M23 <filename>` | not implemented/tried | same |
| Calibration data | `M650` | not implemented/tried | same |
| Set nozzle temp (async, T0=right/T1=left) | `M104 S<temp> T<tool>` | **CONFIRMED working** (Creator 4, via `webui/` set-temp) -- webui reported `CMD M104 Received. ok` (the page's `<p>` collapses whitespace, so the actual bytes are almost certainly `CMD M104 Received.\r\nok\r\n`, matching the plain-ack shape already assumed for M25/M24/M26/M146 in `tests/mock_printer_server.py`'s fallback, but that line-break collapse means this isn't a byte-exact capture the way the read commands above are) | [flashforge-api-docs wiki](https://github.com/Parallel-7/flashforge-api-docs/wiki/M-Code-Reference), [FlashForgeEmulator](https://github.com/Parallel-7/FlashForgeEmulator), [OctoPrint-FlashForge G-Code Reference](https://github.com/Mrnt/OctoPrint-FlashForge/wiki/G-Code-Reference) -- three independent sources agree |
| Set bed temp (async) | `M140 S<temp>` | **CONFIRMED working** (Creator 4, via `webui/` and `ff_control.py set-bed-temp`) -- same | same three |
| Set nozzle temp and block until reached | `M109 S<temp> T<tool>` | documented, **not implemented** here -- would block the socket read past the quiet-window heuristic, see "Framing" | [FlashForgeEmulator](https://github.com/Parallel-7/FlashForgeEmulator) |
| Set bed temp and block until reached | `M190 S<temp>` | documented, **not implemented** here, same reason | same |

### Speed / feed rate / flow rate override: doesn't appear to exist

Checked specifically for a Marlin-style `M220` (feed rate override) or
`M221` (flow rate override) equivalent. None of the sources above --
including a project that explicitly emulates both the legacy TCP and
modern JSON protocols -- document anything for adjusting print speed on a
running print, on either port 8899 or port 8898. `G1`'s `F` parameter sets
speed only as baked into the gcode being streamed at slice time, not as a
live override. This looks like a genuine gap in what FlashForge's protocol
exposes (FlashPrint's own network control panel doesn't appear to have a
speed slider either), not something these sources happened to miss --
not implemented here.

`ff_control.py` only wires up the read-only rows plus pause/resume/stop
(gated behind `--confirm`). File upload/start-print (`M28`/`M23`/`M29`,
with a separate 4096-byte-packet/CRC32 binary framing per Slugger2k's docs)
isn't implemented -- out of scope until the read-only commands are confirmed
to work at all, and it overlaps with the `.gx`-over-network transfer problem
which is a separate can of worms from live status/control.

## Don't confuse this with the in-gcode M65x/M108 codes

The parent project's `README.md` documents `M108 Tn`, `M132`, `M652`,
`M653`, `M654`, `M656`, `M6`/`M7` found *inside* the gcode body of a real
`.gx` export -- those are instructions the firmware executes as it streams
the file being printed, baked in by FlashPrint at slice time. They are a
completely different namespace from the commands in this document, which
are sent live over a TCP socket to ask the machine questions or interrupt
whatever it's doing right now. A print started from a `.gx` file will still
contain and execute its own `M65x` codes regardless of what this protocol
does or doesn't support.

## Open questions

- ~~Does the Creator 4 listen on 8899 at all?~~ **Resolved: yes.**
- ~~If it does, does `M601 S1` actually work?~~ **Resolved: yes, no
  check-code or other auth needed** -- at least from the same local network
  the camera stream is on.
- ~~Exact `M115`/`M105`/`M114` response text for this machine~~ **Resolved,
  see "Confirmed from a real session" above.**
- Whether `M25`/`M24`/`M26` (pause/resume/stop) are real on this firmware --
  still untested; needs a real print running to try safely-ish (safely in
  the sense of "worst case you find out stop doesn't work by watching the
  print keep going" -- see `control/README.md` for how to test with the
  least risk).
- ~~Whether `M104`/`M140` (set nozzle/bed temp) are real on this firmware~~
  **Resolved: yes, confirmed working.** Exact raw response text wasn't
  captured this round though (unlike the read commands' verbatim capture
  above) -- running `ff_control.py set-temp`/`set-bed-temp` from a
  terminal prints the raw response, worth pasting in here next time for
  the same level of detail as the reads.
- ~~Whether `M146` (LED on/off) is real on this firmware~~ **Resolved:
  yes, confirmed working.** Same caveat -- raw response text not captured
  yet.
- Whether `M119`'s `CurrentFile:` field populates with a filename during an
  actual print (would make it useful for "what's it printing" without
  needing `M27`).
- Whether other read-only queries behave differently mid-print vs idle
  (e.g. does `M105` show real target temps instead of `/0`, does `M114`
  show real toolhead motion).
- UDP discovery (`225.0.0.9:19000`, mentioned by Slugger2k) -- packet format
  not documented in any source checked, not implemented here. Not needed if
  you already know the IP, which you do.
