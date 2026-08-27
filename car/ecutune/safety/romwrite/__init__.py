"""The ROM write path — clamped edits to a verified flashable image.

Read-only by design elsewhere: `romread/__init__.py` says "Strictly one-directional: bytes in,
numbers out. There is deliberately no write/patch path in this package." This is that path, and
it lives under `safety/` (per docs/OPEN-CHECKLIST.md) so the source-scan invariant in
tests/test_write_path.py keeps covering it.

  checksum.py  SH7058 checksum block: verify + one-pass repair
  encoder.py   engineering values -> raw bytes, via the def's own frexpr, round-trip or refuse
  patcher.py   apply a ClampResult to a ROM copy + the 4-stage verification stack
  report.py    the human CHANGE REPORT Syed reads before anything is flashed

We emit a FILE. We never drive the flash tool — that stays a human act in ECUFlash
(ROADMAP Phase E.5).
"""
from __future__ import annotations

from .checksum import UnknownChecksumLayout
from .encoder import EncodingError, encode
from .patcher import WriteResult, WriteVerificationError, patch
from .report import change_report

__all__ = ["patch", "encode", "change_report", "WriteResult",
           "WriteVerificationError", "EncodingError", "UnknownChecksumLayout"]
