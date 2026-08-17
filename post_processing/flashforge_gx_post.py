#!/usr/bin/env python3
"""
OrcaSlicer post-processing script: wraps a sliced .gcode file into
Flashforge's proprietary .gx container so it can be printed on a Flashforge
Creator 4. Targets a single right extruder (T0) only -- the Creator 4 is
IDEX hardware, but this bridge deliberately doesn't drive the left head or
dual-material / mirror / duplicate modes.

Wire-up (OrcaSlicer: Process Settings > Others):
  - Post-processing scripts: point this at the sibling flashforge_gx_post.bat
    wrapper, NOT this .py file directly. OrcaSlicer launches whatever path
    you give as a program in its own right, and a .py file isn't a valid
    Windows executable (confirmed via testing: fails with Win32 error 193 /
    ERROR_BAD_EXE_FORMAT). The .bat wrapper just calls
    `python flashforge_gx_post.py` internally.
  - Output filename format: end it in `.gx` instead of `.gcode`, e.g.
    `{input_filename_base}_{filament_type[initial_tool]}_{print_time}.gx`
    OrcaSlicer creates the file with that name/extension, then calls this
    script with its path as the last argument; the post-processing contract
    requires the script to read gcode from, and write results back to, that
    same file path.

This is already wired into the process profiles under
orcaslicer_profiles/process/ in this project -- see the project README.md
for first-time setup and orcaslicer_profiles for the machine/process JSON
files this script pairs with.

HEADER LAYOUT: confirmed against TWO real FlashPrint 5 exports for the
Creator 4 (a 20mm calibration cube in ABS, and a fresh right-extruder PLA
print) -- see README "Confirmed from real samples" for how this was derived.
Notable findings:
  - The container embeds TWO preview images, not one: an 80x60 BMP (list-view
    icon) immediately followed by a 320x320 PNG (detail-view render).
  - `multi_extruder_type` is 5 (not 0) for a right-extruder-only print on
    this IDEX machine, and the header's "mode" field is 3 (not 2). Both
    confirmed identical across both real samples; hardcoded below.
  - The trailing header int16 field (see encode_gx below) is NOT confirmed:
    one real sample had 0 there, a second, fresher sample had 257. Meaning
    unknown. Deliberately left hardcoded at 0 (the first-validated value)
    rather than guessed at -- see the comment at that line and the README
    "Open Questions".

Adapted from urself25/Orca_Gcode_to_Gx (GPL-3.0):
https://github.com/urself25/Orca_Gcode_to_Gx
"""

import base64
import struct
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

ICON_SIZE = (80, 60)
PREVIEW_SIZE = (320, 320)

# Gcode footer comment keys OrcaSlicer emits. Nozzle temp is the one key
# that's been observed to vary between OrcaSlicer versions/profile
# inheritance chains -- some emit plain "temperature", others
# "nozzle_temperature" -- so both are accepted defensively.
KEY_PRINT_TIME = "; estimated printing time (normal mode) ="
KEY_FILAMENT_MM = "; filament used [mm] ="
KEY_LAYER_HEIGHT = "; layer_height ="
# NOT "; machine_max_speed_x =" -- confirmed against a real OrcaSlicer test
# slice that this key just echoes the printer profile's configured speed
# LIMIT (500mm/s in these profiles), not anything resembling an actual print
# speed -- it produced a nonsense 500mm/s header value. outer_wall_speed is
# OrcaSlicer's closest analog to FlashPrint's own "base_print_speed" comment
# (the wall/perimeter speed, the most representative single "how fast is
# this printing" number), and is a per-process, not per-printer, setting.
KEY_PRINT_SPEED = "; outer_wall_speed ="
KEY_BED_TEMP = "; first_layer_bed_temperature ="
KEY_NOZZLE_TEMP_CANDIDATES = ("; temperature =", "; nozzle_temperature =")


class GXWriter:
    def __init__(self, gcode_path: Path):
        self.gcode_path = gcode_path
        self.gcode_lines: list[str] = []
        self.icon_bmp: bytes = b""
        self.preview_png: bytes = b""

        self.print_time = 0
        self.filament_usage = 0
        self.layer_height = 0
        self.print_speed = 60
        self.bed_temp = 0
        self.print_temp = 0

        # Forced constants: single right (T0) extruder only. Values below are
        # copied from real Creator 4 FlashPrint 5 exports for right-only
        # prints, not derived -- see module docstring.
        self.multi_extruder_type = 5
        self.filament_usage_left = 0
        self.header_mode_field = 3

        self._load_gcode()
        self._extract_metadata()
        source_image = self._extract_source_image()
        self.icon_bmp = self._render_icon(source_image)
        self.preview_png = self._render_preview(source_image)

    def _load_gcode(self) -> None:
        with open(self.gcode_path, "r", encoding="utf-8", errors="ignore") as f:
            self.gcode_lines = f.readlines()

    def _extract_metadata(self) -> None:
        for line in self.gcode_lines:
            stripped = line.strip()

            if stripped.startswith(KEY_PRINT_TIME):
                self.print_time = self._parse_duration(stripped.split("=", 1)[1])

            elif stripped.startswith(KEY_FILAMENT_MM):
                value = stripped.split("=", 1)[1].strip().split(",")[0].strip()
                self.filament_usage = int(float(value))

            elif stripped.startswith(KEY_LAYER_HEIGHT):
                self.layer_height = int(float(stripped.split("=", 1)[1].strip()) * 1000)

            elif stripped.startswith(KEY_PRINT_SPEED):
                value = stripped.split("=", 1)[1].strip().split(",")[0].strip()
                if value:
                    self.print_speed = int(float(value))

            elif stripped.startswith(KEY_BED_TEMP):
                value = stripped.split("=", 1)[1].strip().split(",")[0].strip()
                if value:
                    self.bed_temp = int(float(value))

            elif stripped.startswith(KEY_NOZZLE_TEMP_CANDIDATES):
                value = stripped.split("=", 1)[1].strip().split(",")[0].strip()
                if value:
                    self.print_temp = int(float(value))

    @staticmethod
    def _parse_duration(text: str) -> int:
        h = m = s = 0
        for part in text.strip().split():
            if part.endswith("h"):
                h = int(part[:-1])
            elif part.endswith("m"):
                m = int(part[:-1])
            elif part.endswith("s"):
                s = int(part[:-1])
        return h * 3600 + m * 60 + s

    def _extract_source_image(self) -> Image.Image:
        """Pull OrcaSlicer's embedded gcode-viewer thumbnail (a flat
        snapshot, not a 3D render) to reuse as the basis for both preview
        images. Falls back to a solid grey placeholder if none is found or
        it fails to decode -- this only affects what's shown on the
        printer's screen, not whether the print itself works."""
        base64_png = []
        inside = False
        for line in self.gcode_lines:
            if "thumbnail begin" in line:
                inside = True
                continue
            if "thumbnail end" in line:
                break
            if inside:
                base64_png.append(line.strip().lstrip(";").strip())

        if base64_png:
            try:
                png_bytes = base64.b64decode("".join(base64_png))
                return Image.open(BytesIO(png_bytes)).convert("RGB")
            except Exception as exc:
                print(f"flashforge_gx_post: could not decode embedded thumbnail ({exc}); using placeholder", file=sys.stderr)

        return Image.new("RGB", PREVIEW_SIZE, color=(60, 60, 60))

    @staticmethod
    def _render_icon(source: Image.Image) -> bytes:
        """80x60 BMP list-view icon (size confirmed from real Creator 4
        exports). Stretched to fit -- FlashPrint's own icon is this exact
        aspect ratio so no letterboxing is needed here."""
        image = source.resize(ICON_SIZE)
        out = BytesIO()
        image.save(out, format="BMP")
        return out.getvalue()

    @staticmethod
    def _render_preview(source: Image.Image) -> bytes:
        """320x320 PNG detail-view preview (dimensions confirmed from real
        Creator 4 exports). Letterboxed onto a black square rather than
        stretched, since the source thumbnail's aspect ratio generally
        won't match a 1:1 square."""
        image = ImageOps.pad(source, PREVIEW_SIZE, color=(0, 0, 0))
        out = BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()

    def encode_gx(self) -> bytes:
        # NOTE: tool selection (M108 T0) is expected to already be present,
        # emitted by the printer profile's machine_start_gcode -- Flashforge
        # firmware doesn't recognize bare "T0"/"T1" (confirmed: real Creator
        # 4 exports never use them, only "M108 Tn"), so there's nothing
        # useful for this script to inject here.
        gcode_bytes = "".join(self.gcode_lines).encode("latin-1", errors="ignore")

        magic = b"xgcode 1.0\n\0"
        fixed_header_size = len(magic) + 16 + 14 + 16  # = 58, matches real samples exactly
        bmp_offset = fixed_header_size
        png_offset = bmp_offset + len(self.icon_bmp)
        gcode_offset = png_offset + len(self.preview_png)

        header = magic
        header += struct.pack("<4i", 0, bmp_offset, png_offset, gcode_offset)
        header += struct.pack(
            "<iiih",
            max(self.print_time, 1),
            self.filament_usage,
            self.filament_usage_left,
            self.multi_extruder_type,
        )
        # Trailing header field (last of the 8 int16s below), meaning
        # unconfirmed. Hardcoded to 0 -- the value seen in the real ABS
        # Creator 4 sample this format was reverse-engineered from. A real
        # PLA sample showed 257 (0x0101) here instead -- the same ABS/PLA
        # split seen in the M651/M652 case-fan and M653/M656 chamber-heat
        # codes (see machine_start_gcode in the printer profiles), so this
        # may mirror the case-fan on/off state into the header for the LCD.
        # Deliberately not acted on: unconfirmed, and this script has no way
        # to detect a filament-level fan-override gcode snippet the way it
        # reads printer/process settings from OrcaSlicer's footer comments.
        # See docs/NOZZLE_VARIANT_TABLE.md item 2. If you find out what this
        # field means, update here.
        header += struct.pack(
            "<8h",
            self.layer_height, 0, self.header_mode_field,
            self.print_speed, self.bed_temp, self.print_temp, self.print_temp, 0,
        )
        assert len(header) == fixed_header_size, f"header size drifted: {len(header)} != {fixed_header_size}"
        return header + self.icon_bmp + self.preview_png + gcode_bytes

    def save(self) -> None:
        data = self.encode_gx()
        temp_path = self.gcode_path.with_suffix(self.gcode_path.suffix + ".tmp")
        temp_path.write_bytes(data)
        temp_path.replace(self.gcode_path)
        print(f"flashforge_gx_post: wrote {len(data)} bytes to {self.gcode_path}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: flashforge_gx_post.py <sliced.gcode>", file=sys.stderr)
        sys.exit(1)

    # OrcaSlicer's post-processing contract passes the file path as the
    # last argument; use argv[-1] rather than argv[1] to be robust to any
    # extra flags OrcaSlicer may prepend.
    gcode_path = Path(sys.argv[-1])
    if not gcode_path.exists():
        print(f"flashforge_gx_post: no such file: {gcode_path}", file=sys.stderr)
        sys.exit(1)

    GXWriter(gcode_path).save()


if __name__ == "__main__":
    main()
