#!/usr/bin/env python3
"""
End-to-end structural test: builds the synthetic fixture, runs it through
flashforge_gx_post.py, and validates the result with validate_gx.py.

This proves the *pipeline* is wired together correctly (metadata parsing,
thumbnail conversion, binary packing, file structure). It does NOT prove
the output will print on a real Creator 4 -- see README.md "Open Questions"
and "First-time setup" for the real hardware test.

Usage: python tests/run_structural_test.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POST_PROCESSING = ROOT / "post_processing"
SAMPLES = ROOT / "tests" / "samples"


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(str(c) for c in cmd)}")
    subprocess.run(cmd, check=True)


def main() -> None:
    run([sys.executable, str(ROOT / "tests" / "make_fixture.py")])

    src = SAMPLES / "test_input.gcode"
    dst = SAMPLES / "test_output.gx"
    shutil.copyfile(src, dst)

    run([sys.executable, str(POST_PROCESSING / "flashforge_gx_post.py"), str(dst)])
    run([sys.executable, str(POST_PROCESSING / "validate_gx.py"), str(dst)])

    print("\nstructural test passed")


if __name__ == "__main__":
    main()
