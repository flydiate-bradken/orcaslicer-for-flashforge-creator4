#!/usr/bin/env python3
"""
Structural check for a .gx file produced by flashforge_gx_post.py.

This only verifies the file is well-formed (magic bytes present, header
fields decode to sane values, both embedded preview images are valid,
gcode body is non-empty and looks like gcode). It CANNOT verify the file
will actually print correctly on a Creator 4 -- that needs a real print
test (see README.md "First-time setup").

Header field offsets/order confirmed against two real Creator 4 FlashPrint 5
exports (see README "Confirmed from real samples"): the container embeds
TWO preview images (an 80x60 BMP icon, then a 320x320 PNG), and the header's
4 leading int32 fields are (reserved, bmp_offset, png_offset, gcode_offset)
-- i.e. they're authoritative offsets to trust directly, not values to
independently re-derive from image sizes.

Usage: validate_gx.py <file.gx>
"""

import struct
import sys
from pathlib import Path

MAGIC = b"xgcode 1.0\n\0"
HEADER_SIZE = len(MAGIC) + 16 + 14 + 16  # magic + 4x int32 + (iiih) + (8h) = 58


def validate(path: Path) -> list[str]:
    errors = []
    data = path.read_bytes()

    if len(data) < HEADER_SIZE:
        return [f"file too short ({len(data)} bytes) to contain a full header"]

    if data[: len(MAGIC)] != MAGIC:
        errors.append(f"bad magic bytes: {data[: len(MAGIC)]!r} (expected {MAGIC!r})")

    offset = len(MAGIC)
    reserved0, bmp_offset, png_offset, gcode_offset = struct.unpack_from("<4i", data, offset)
    offset += 16
    print_time, filament_mm, filament_mm_left, multi_extruder_type = struct.unpack_from("<iiih", data, offset)
    offset += 14
    (layer_height, reserved1, header_mode_field, print_speed,
     bed_temp, nozzle_temp, nozzle_temp_dup, reserved4) = struct.unpack_from("<8h", data, offset)
    offset += 16

    print("-- header --")
    print(f"  bmp_offset               = {bmp_offset}")
    print(f"  png_offset               = {png_offset}")
    print(f"  gcode_offset             = {gcode_offset}")
    print(f"  print_time               = {print_time}s")
    print(f"  filament_usage_mm        = {filament_mm} (left head: {filament_mm_left})")
    print(f"  multi_extruder_type      = {multi_extruder_type} (expected 5 for right-only on this IDEX machine)")
    print(f"  layer_height             = {layer_height} um")
    print(f"  header_mode_field        = {header_mode_field} (expected 3)")
    print(f"  print_speed              = {print_speed} mm/s")
    print(f"  bed_temp                 = {bed_temp} C")
    print(f"  nozzle_temp              = {nozzle_temp} C (dup field: {nozzle_temp_dup})")
    print(f"  trailing reserved field  = {reserved4} (unconfirmed meaning -- 0 or 257 both seen in real samples)")

    if bmp_offset != HEADER_SIZE:
        errors.append(f"bmp_offset {bmp_offset} != fixed header size {HEADER_SIZE}")
    if print_time <= 0:
        errors.append("print_time is <= 0")
    if filament_mm <= 0:
        errors.append("filament_usage_mm is <= 0 (thumbnail/metadata parsing likely failed)")
    if not (0 <= bed_temp <= 150):
        errors.append(f"bed_temp {bed_temp} outside sane range 0-150C")
    if not (0 <= nozzle_temp <= 400):
        errors.append(f"nozzle_temp {nozzle_temp} outside sane range 0-400C")
    if layer_height <= 0 or layer_height > 1000:
        errors.append(f"layer_height {layer_height}um outside sane range")

    bmp_magic = data[bmp_offset : bmp_offset + 2]
    if bmp_magic != b"BM":
        errors.append(f"no valid BMP magic at bmp_offset {bmp_offset}: {bmp_magic!r}")
    else:
        bmp_declared_size = struct.unpack_from("<I", data, bmp_offset + 2)[0]
        print(f"  bmp size (declared/actual) = {bmp_declared_size} / {png_offset - bmp_offset}")
        if bmp_offset + bmp_declared_size != png_offset:
            errors.append(
                f"BMP declared size ({bmp_declared_size}) doesn't reach png_offset "
                f"({png_offset - bmp_offset} bytes actually available)"
            )

    png_magic = data[png_offset : png_offset + 8]
    if png_magic != b"\x89PNG\r\n\x1a\n":
        errors.append(f"no valid PNG magic at png_offset {png_offset}: {png_magic!r}")
    else:
        print(f"  png size (actual)          = {gcode_offset - png_offset} bytes")

    if gcode_offset >= len(data):
        errors.append("gcode_offset is past end of file")
    else:
        gcode_body = data[gcode_offset:]
        preview = gcode_body[:200].decode("latin-1", errors="ignore")
        print(f"  gcode body length = {len(gcode_body)} bytes")
        print(f"  gcode body preview:\n{preview!r}")
        if b"\nG" not in gcode_body and b"\nM" not in gcode_body:
            errors.append("gcode body doesn't look like gcode (no G/M command lines found)")

    return errors


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: validate_gx.py <file.gx>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    errors = validate(path)

    print()
    if errors:
        print(f"FAILED: {len(errors)} issue(s)")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("OK: structurally valid")


if __name__ == "__main__":
    main()
