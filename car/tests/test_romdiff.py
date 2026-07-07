"""rom-diff: identical images, a single-cell edit, and out-of-table byte changes."""
from __future__ import annotations

import struct

import pytest

from ecutune.romread.diff import diff_roms, format_report

# Reuse the synthetic def pack + ROM builder from the romread tests.
from tests.test_romread import BASE_XML, REV_XML, _build_rom
from ecutune.romread import EcuFlashDefs

SEM = {"fuel.injector_flow": "Injector Flow Scaling",
       "fuel.injector_latency": "Injector Latency"}


@pytest.fixture()
def env(tmp_path):
    (tmp_path / "base.xml").write_text(BASE_XML)
    (tmp_path / "rev.xml").write_text(REV_XML)
    defs = EcuFlashDefs(tmp_path)
    a = tmp_path / "a.bin"
    a.write_bytes(_build_rom())
    return defs, tmp_path, a


def test_identical_roms(env):
    defs, tmp, a = env
    b = tmp / "b.bin"
    b.write_bytes(_build_rom())
    d = diff_roms(a, b, defs, ["TESTREV"], SEM)
    assert d.is_identical and d.byte_diff_count == 0 and not d.table_diffs
    assert "IDENTICAL" in format_report(d)


def test_single_cell_edit_detected_and_attributed(env):
    defs, tmp, a = env
    rom = bytearray(_build_rom())
    struct.pack_into(">f", rom, 0x10, 2707090 / 560.0)      # flow scalar 550 -> 560 cc/min
    b = tmp / "b.bin"
    b.write_bytes(bytes(rom))
    d = diff_roms(a, b, defs, ["TESTREV"], SEM)
    assert not d.is_identical
    assert [t.semantic_id for t in d.table_diffs] == ["fuel.injector_flow"]
    t = d.table_diffs[0]
    assert t.n_diff == 1
    (idx, va, vb), = t.examples
    assert va == pytest.approx(550.0, rel=1e-4) and vb == pytest.approx(560.0, rel=1e-4)
    assert "fuel.injector_flow" in format_report(d)


def test_byte_only_fallback(env):
    from ecutune.romread.diff import byte_only_diff
    defs, tmp, a = env
    rom = bytearray(_build_rom())
    rom[0x12] ^= 0xFF
    b = tmp / "b.bin"
    b.write_bytes(bytes(rom))
    d = byte_only_diff(a, b)
    assert d.byte_diff_count == 1 and not d.table_diffs and not d.is_identical


def test_out_of_table_change_not_hidden(env):
    defs, tmp, a = env
    rom = bytearray(_build_rom())
    rom[0x30] ^= 0xFF                                        # byte outside any defined table
    b = tmp / "b.bin"
    b.write_bytes(bytes(rom))
    d = diff_roms(a, b, defs, ["TESTREV"], SEM)
    assert d.byte_diff_count == 1 and not d.table_diffs
    assert "OUTSIDE the semantic table set" in format_report(d)
