# Getting real ground truth: capturing a FlashPrint 5 control session

This is the same kind of step that unlocked the `.gx` work one level up
(a real sample beats every published write-up combined). For live control,
the equivalent is a packet capture of FlashPrint 5 actually talking to the
Creator 4 over the network.

## What to capture

On the PC running FlashPrint 5, while it's connected to the Creator 4 over
WiFi/Ethernet (not USB):

1. Install [Wireshark](https://www.wireshark.org/) if you don't have it.
2. Start a capture filtered to just the printer, e.g.
   `host 172.16.128.123` (swap in the real IP) -- this keeps the capture
   small and avoids picking up unrelated traffic.
3. In FlashPrint, connect to the machine over the network and, one at a
   time with a pause between each so they're easy to pick out later:
   - just connect and let it sit for a few seconds (captures whatever
     handshake/login happens)
   - read status/temperature (whatever FlashPrint shows automatically)
   - if convenient: start a print, let it run a few seconds, pause it,
     resume it, then stop it
   - disconnect
4. Stop the capture, save as `.pcapng`.

## What actually matters from it

The pcap itself is fine to keep as-is (it's just local traffic between your
PC and the printer on your own LAN, no external endpoints), but what's
actually useful for updating `PROTOCOL_NOTES.md` is much smaller: for each
request/response pair on port 8899 (or whatever port FlashPrint actually
uses -- that's worth confirming too), the raw ASCII text sent each
direction. In Wireshark: right-click a TCP segment on the printer's port →
**Follow → TCP Stream** shows the whole exchange as text in one view, which
is the easiest thing to copy out.

If FlashPrint turns out to use port 8898 or something else entirely instead
of 8899, that alone is a useful (if deflating) finding -- it means the
legacy-protocol guess in `PROTOCOL_NOTES.md` was wrong and the modern JSON
API (or something undocumented) is the real answer for this machine.

## Once you have it

Share the follow-TCP-stream text (or the whole .pcapng) back here.
`PROTOCOL_NOTES.md` and `ff_control.py` get corrected against whatever it
actually shows -- same loop as `scripts/flashforge_gx_post.py` did against
`samples/real_creator4_20mm_box.gx`.
