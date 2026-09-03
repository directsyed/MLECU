"""The ROM write path, the safety-critical build.

`romread/__init__.py` states the read package is "strictly one-directional: bytes in, numbers
out. There is deliberately no write/patch path in this package." These tests cover the path that
does write, and they are deliberately adversarial: most assert that something is REFUSED.
"""
from __future__ import annotations

import pathlib

import numpy as np
import pytest

from ecutune.core.models import CellEdit, ClampResult, Table
from ecutune.platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
from ecutune.romread import EcuFlashDefs, RomImage, read_semantic_tables
from ecutune.romread.reader import ResolvedDef
from ecutune.safety.romwrite import EncodingError, WriteVerificationError, encode, patch
from ecutune.safety.romwrite import checksum as ck
from ecutune.safety.romwrite.patcher import _diff_ranges
from ecutune.simulation.rom_seed import DEFAULT_DEFS, SIBLING_DEFS

MAF = "sensor.maf_transfer"
# car/tests/ -> car/ -> car/ecu/rom read/ : the archived read of THIS car's ECU
ROM_PATH = pathlib.Path(__file__).resolve().parents[1] / "ecu" / "rom read"


def _rom_bytes():
    hits = sorted(ROM_PATH.glob("*.bin"))
    if not hits:
        pytest.skip("no archived ROM read available")
    return hits[0].read_bytes()


@pytest.fixture(scope="module")
def rom():
    data = _rom_bytes()
    defs = EcuFlashDefs(DEFAULT_DEFS)
    tables, report = read_semantic_tables(RomImage(data), defs, list(SIBLING_DEFS),
                                          TO_PLATFORM, VARIANTS)
    return data, defs, tables, report


def _result(edits):
    return ClampResult(True, tuple(edits))


# ---------------------------------------------------------------- checksum

def test_stock_rom_satisfies_the_checksum_invariant(rom):
    data, *_ = rom
    assert ck.verify(data) == [], "the archived stock read should be internally consistent"
    assert len(ck.read_records(data)) >= 1


def test_checksum_repair_is_a_one_pass_fixed_point(rom):
    """Corrupt a covered byte, confirm detection, repair, confirm ONE pass suffices."""
    data, *_ = rom
    buf = bytearray(data)
    buf[0xCB75C] ^= 0xFF
    assert len(ck.verify(buf)) == 1
    assert len(ck.repair(buf)) == 1
    assert ck.verify(buf) == []
    assert ck.repair(buf) == [], "a second pass should find nothing left to do"


def test_checksum_refuses_an_unrecognised_block():
    """A block that is not ours raises rather than returning a confident wrong answer."""
    junk = bytearray(1024 * 1024)
    junk[0xFFB80:0xFFB8C] = bytes.fromhex("25033107 00005560 DEADBEEF".replace(" ", ""))
    with pytest.raises(ck.UnknownChecksumLayout):
        ck.read_records(junk)


# ---------------------------------------------------------------- encoder

def test_encoder_round_trips_every_scaling_our_tables_use(rom):
    _, defs, tables, report = rom
    for sem_id, t in tables.items():
        sc = report["resolved"][sem_id].scaling
        vals = np.asarray(t.values, float).ravel()[:8]
        blob, err = encode(vals, sc)
        assert len(blob) == vals.size * sc.byte_size
        assert err <= max(abs(vals).max() * 1e-6, 1e-3), f"{sem_id} round-trip drifted"


def test_encoder_refuses_rather_than_approximating(rom):
    _, _, _, report = rom
    latency = report["resolved"]["fuel.injector_latency"].scaling
    with pytest.raises(EncodingError, match="out of range"):
        encode(np.array([9999.0]), latency)
    with pytest.raises(EncodingError, match="non-finite"):
        encode(np.array([np.nan]), report["resolved"][MAF].scaling)


# ---------------------------------------------------------------- patcher

def test_patch_changes_only_the_edited_cells_and_the_checksum(rom):
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    edits = [CellEdit(MAF, 0, i, float(stock[i] * 1.10)) for i in (16, 17, 18)]
    w = patch(data, _result(edits), tables, report["resolved"])

    maf_lo = report["resolved"][MAF].table_def.address
    maf_hi = maf_lo + stock.size * report["resolved"][MAF].scaling.byte_size
    cks = ck.block_offset(data)
    for lo, hi in w.byte_ranges:
        in_table = maf_lo <= lo and hi <= maf_hi
        in_cksum = cks <= lo and hi <= cks + 12 * 32
        assert in_table or in_cksum, f"stray write at 0x{lo:X}..0x{hi:X}"
    assert w.checksum_repaired == (0,)


def test_readback_returns_exactly_what_was_intended(rom):
    data, defs, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    want = stock.copy()
    for i in (20, 21, 22):
        want[i] = stock[i] * 1.10
    edits = [CellEdit(MAF, 0, i, float(want[i])) for i in (20, 21, 22)]
    w = patch(data, _result(edits), tables, report["resolved"])

    back, _ = read_semantic_tables(RomImage(w.data), defs, list(SIBLING_DEFS),
                                   TO_PLATFORM, VARIANTS)
    got = np.asarray(back[MAF].values, float).ravel()
    assert np.allclose(got, want, rtol=1e-6)
    for sem_id in tables:
        if sem_id != MAF:
            assert np.array_equal(tables[sem_id].values, back[sem_id].values), \
                f"{sem_id} moved and should not have"


def test_patched_rom_still_passes_its_own_checksum(rom):
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    w = patch(data, _result([CellEdit(MAF, 0, 19, float(stock[19] * 1.10))]),
              tables, report["resolved"])
    assert ck.verify(w.data) == []


def test_patch_refuses_an_aborted_proposal(rom):
    data, _, tables, report = rom
    aborted = ClampResult(False, (), (), aborted_by="knock_auto_abort")
    with pytest.raises(WriteVerificationError, match="aborted"):
        patch(data, aborted, tables, report["resolved"])


def test_patch_refuses_without_a_resolved_def(rom):
    """The address MUST come from reconciliation. A2WC412D puts the MAF curve +0x20 away, so a
    writer that re-derived the address from a fixed def id would corrupt a neighbouring table."""
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    with pytest.raises(WriteVerificationError, match="reconciliation"):
        patch(data, _result([CellEdit(MAF, 0, 19, float(stock[19] * 1.1))]), tables, {})


def test_patch_refuses_when_ordering_dies_in_the_encoding(rom):
    """A guarantee that does not survive the storage type is not a guarantee.

    Ask for two adjacent cells separated by far less than float32 can represent: in engineering
    units the curve is still ascending, but the written bytes are equal.
    """
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    edits = [CellEdit(MAF, 0, 19, float(stock[20]) - 1e-9)]
    with pytest.raises(WriteVerificationError, match="ENCODED curve is not"):
        patch(data, _result(edits), tables, report["resolved"])


def test_patch_refuses_a_cell_lifted_past_its_neighbour(rom):
    """Adjacent MAF breakpoints sit ~13-15% apart, so a single-cell bump larger than that
    inverts the curve. The write path refuses it even though each individual value is sane."""
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    assert stock[19] * 1.25 > stock[20], "test premise: 25% must overshoot the neighbour"
    with pytest.raises(WriteVerificationError, match="ENCODED curve is not"):
        patch(data, _result([CellEdit(MAF, 0, 19, float(stock[19] * 1.25))]),
              tables, report["resolved"])


def test_stray_byte_is_detected_by_the_diff(rom):
    data, *_ = rom
    tampered = bytearray(data)
    tampered[0x40000] ^= 0xFF
    assert _diff_ranges(data, bytes(tampered)) == [(0x40000, 0x40001)]


def test_patch_never_mutates_the_stock_image(rom):
    data, _, tables, report = rom
    stock = np.asarray(tables[MAF].values, float).ravel()
    before = bytes(data)
    patch(data, _result([CellEdit(MAF, 0, 19, float(stock[19] * 1.1))]), tables,
          report["resolved"])
    assert data == before
