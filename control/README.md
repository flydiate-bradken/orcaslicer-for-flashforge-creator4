# Creator 4 live control (status / camera / start-stop) from a browser

Companion tool to the `.gx` bridge in the parent folder. That work lets
OrcaSlicer *produce* a file the Creator 4 will print. This folder is about
the other half of what FlashPrint 5 does: connect to the machine live over
the network to see status, watch the camera, and start/pause/stop/adjust
temperatures — without opening FlashPrint. Neither vanilla OrcaSlicer nor
Flashforge's own OrcaSlicer fork support the Creator 4 for this.

## Status

Confirmed working against a real Creator 4 (`Creator4S`, firmware V1.0.0)
over the local network: login/logout, all five read-only queries
(`info`/`temp`/`status`/`progress`/`position`), `set-temp`/`set-bed-temp`,
`led-on`/`led-off`, and the camera stream — see `PROTOCOL_NOTES.md` for
command-level detail. **Still unconfirmed**: `pause`/`resume`/`stop`
(`M25`/`M24`/`M26`) — these need an actual print running to test
meaningfully, so treat them as a hypothesis until tried against a real
in-progress print.

<details>
<summary>Why not just use OrcaSlicer or Flashforge's own tools?</summary>

- Vanilla OrcaSlicer has no Flashforge device support at all (no camera/
  status/control tab for any Flashforge printer).
- Flashforge's own OrcaSlicer fork ("Orca-Flashforge" / "Flash Studio"), which
  *does* add exactly this (camera + status + start/stop/pause + temps),
  explicitly only supports the Adventurer 5M family, AD5X, Guider 3 Ultra,
  and Creator 5 -- same gap as the `.gx` export problem one level up. Nobody
  has asked for Creator 4 support there yet (checked the open GitHub issues).
- Community projects that do this for other Flashforge printers
  ([`FlashForgeWebUI`](https://github.com/Parallel-7/FlashForgeWebUI),
  [`flashforge-finder-api`](https://github.com/01F0/flashforge-finder-api))
  don't list the Creator 4 or any IDEX machine either.

So this is the same situation as the `.gx` container: no first-party or
community support for this specific machine, but the underlying protocol
is a known, documented (if not Creator-4-confirmed) thing.
</details>

## What's here

```
PROTOCOL_NOTES.md         command reference for the legacy TCP 8899 protocol,
                           with sources and confirmed-vs-assumed call-outs
ff_control.py              stdlib-only Python client + CLI for that protocol
tests/mock_printer_server.py  fake printer that speaks the documented protocol,
                               for testing ff_control.py without real hardware
tests/run_control_smoke_test.py   runs ff_control.py against the mock server
captures/README.md         what to capture from a real FlashPrint session,
                            and how, to confirm the remaining unconfirmed pieces
webui/server.py             local browser status page -- see "Browser status page" below
webui/static/                its HTML/CSS/JS
```

## Browser status page

```
python control/webui/server.py 172.16.128.123
```

then open **http://localhost:8000**. A small local (stdlib-only, no extra
dependencies) Python HTTP server that:

- polls the printer over `ff_control.py`'s TCP client and exposes the
  result as JSON at `/api/status` (browsers can't open raw TCP sockets, so
  this is the bridge)
- serves a page that polls that endpoint every 3s and shows machine info,
  live temps (T0/T1/bed, current vs. target), print progress, and status
- embeds your existing camera stream via `<iframe>` alongside it -- no
  separate camera setup needed

Runs entirely on your machine and only talks to the printer on your LAN --
nothing goes further than that. Reads, temperature control, and LED are
all confirmed end-to-end against the real printer. Options:

```
python control/webui/server.py 172.16.128.123 --web-port 9000
python control/webui/server.py 172.16.128.123 --camera-url http://172.16.128.123:8080/stream_simple.html
```

**"Set temperature" card**: separate Right (T0) and Left (T1) nozzle
fields plus a Bed field, each with its own Set button -- POSTs to
`/api/set-temp` / `/api/set-bed-temp`, sending `M104`/`M140`. Confirmed
working. Every Set button still pops a browser `confirm()` first
(mirroring `ff_control.py`'s `--confirm` flag -- these act on the real
heaters immediately, confirmed or not), and the server clamps input to a
sane range (0-280°C nozzle, 0-130°C bed) before sending anything.

**"Lights" card**: single toggle button (`POST /api/led-on` /
`/api/led-off`, sending `M146`), confirmed working. No confirm prompt in
front of it -- worst case is a light that doesn't change rather than
anything touching the print or the heaters.

Still no pause/resume/stop buttons -- those are unconfirmed and not wired
in yet.

## Testing without a printer

```
python control/tests/run_control_smoke_test.py
```

Spins up a local mock TCP server that answers with the canned responses
documented in `PROTOCOL_NOTES.md`, then runs `ff_control.py`'s client
against it and checks the round trip. This proves the client is wired up
correctly (framing, parsing); it proves **nothing** about whether a real
Creator 4 actually speaks this protocol or returns these strings.

## Using it against the real printer

While on the same network as the printer, the read-only commands are
confirmed working:

```
python control/ff_control.py 172.16.128.123 info
python control/ff_control.py 172.16.128.123 temp
python control/ff_control.py 172.16.128.123 status
python control/ff_control.py 172.16.128.123 progress
python control/ff_control.py 172.16.128.123 position
```

`set-temp`/`set-bed-temp` and `led-on`/`led-off` are confirmed working;
`pause`/`resume`/`stop` are implemented but still unconfirmed. All of them
are gated behind `--confirm` since they act on a real, possibly mid-print
machine:

```
python control/ff_control.py 172.16.128.123 pause --confirm
python control/ff_control.py 172.16.128.123 set-temp --tool 0 --celsius 220 --confirm
python control/ff_control.py 172.16.128.123 set-bed-temp --celsius 60 --confirm
python control/ff_control.py 172.16.128.123 led-on --confirm
python control/ff_control.py 172.16.128.123 led-off --confirm
```

**Be ready to use the front panel or FlashPrint to intervene if the
printer doesn't do what's expected** when trying `pause`/`resume`/`stop`
-- unlike everything else at this point, those haven't been checked
against real behavior yet, and specifically need an active print to test
against meaningfully.

## Confirming pause/resume/stop

The only piece of the core protocol left to confirm: next time a print is
running, try `pause --confirm`, then (if it actually paused) `resume
--confirm`, and see what the printer actually does. If it doesn't behave as
expected, a real packet capture of FlashPrint 5 doing the same actions
(`captures/README.md`) will show what it sends instead. Once confirmed,
pause/resume/stop buttons can be added to `webui/` the same way the
existing temperature/lights controls work.
