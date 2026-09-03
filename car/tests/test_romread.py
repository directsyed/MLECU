"""romread: def merging, value decoding, and the cross-def reconciliation guard.

Uses a tiny synthetic def pair + hand-built ROM bytes so the tests carry no dependency on the
gitignored SubaruDefs/ROM downloads; the real A2WC411D read is exercised by the integration
test at the bottom, which SKIPS when the data files are absent (fresh clone).
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from ecutune.platforms.subaru_ecuflash import TO_PLATFORM, VARIANTS
from ecutune.romread import EcuFlashDefs, RomImage, read_semantic_tables, read_table
from ecutune.romread.defs import Scaling
from ecutune.romread.reader import plausible

BASE_XML = """<rom>
  <romid><xmlid>TESTBASE</xmlid></romid>
  <scaling name="flow" storagetype="float" endian="big" toexpr="2707090/x" min="231.65" max="1000" units="cc/min"/>
  <scaling name="ms" storagetype="uint16" endian="big" toexpr="x*.00025" min="0.3" max="6" units="ms"/>
  <scaling name="volts" storagetype="float" endian="big" toexpr="x" units="V"/>
  <table name="Injector Flow Scaling" type="2D" scaling="flow">
    <table name="" type="Static Y Axis" elements="1"><data>Injector Flow Constant</data></table>
  </table>
  <table name="Injector Latency" type="2D" scaling="ms">
    <table name="Battery Output" type="Y Axis" elements="3" scaling="volts"/>
  </table>
</rom>"""

REV_XML = """<rom>
  <romid>
    <xmlid>TESTREV</xmlid>
    <internalidaddress>0</internalidaddress>
    <internalidstring>TESTREV1</internalidstring>
    <ecuid>1234</ecuid>
  </romid>
  <include>TESTBASE</include>
  <table name="Injector Flow Scaling" address="10"/>
  <table name="Injector Latency" address="20"><table name="Y" address="14"/></table>
</rom>"""

# Same base, latency shifted to a WRONG address (revision drift): reads garbage.
REV_DRIFT_XML = REV_XML.replace("TESTREV1", "TESTREV2").replace("TESTREV</xmlid>", "TESTDRIFT</xmlid>") \
                       .replace('"Injector Latency" address="20"', '"Injector Latency" address="26"') \
                       .replace('name="Y" address="14"', 'name="Y" address="8"')


def _build_rom() -> bytes:
    rom = bytearray(64)
    rom[0:8] = b"TESTREV1"
    struct.pack_into(">f", rom, 0x10, 2707090 / 550.0)              # flow scalar -> 550 cc/min
    struct.pack_into(">fff", rom, 0x14, 8.0, 11.0, 14.0)            # volts axis ascending
    for i, ms in enumerate((2.0, 1.2, 0.7)):                        # latency curve @0x20
        struct.pack_into(">H", rom, 0x20 + 2 * i, int(ms / 0.00025))
    return bytes(rom)


@pytest.fixture()
def defs(tmp_path: Path) -> EcuFlashDefs:
    (tmp_path / "base.xml").write_text(BASE_XML)
    (tmp_path / "rev.xml").write_text(REV_XML)
    (tmp_path / "drift.xml").write_text(REV_DRIFT_XML)
    return EcuFlashDefs(tmp_path)


def test_merge_and_decode(defs):
    rom = RomImage(_build_rom())
    tables, scalings = defs.tables("TESTREV")
    flow = read_table(rom, tables["Injector Flow Scaling"], scalings)
    assert flow.kind == "scalar"
    assert float(flow.values) == pytest.approx(550.0, rel=1e-4)
    lat = read_table(rom, tables["Injector Latency"], scalings)
    assert lat.kind == "curve_1d"
    assert list(lat.x_axis.breakpoints) == pytest.approx([8.0, 11.0, 14.0])
    assert lat.values == pytest.approx([2.0, 1.2, 0.7], rel=1e-3)


def test_reconciliation_prefers_unique_plausible(defs):
    rom = RomImage(_build_rom())
    sem_map = {"fuel.injector_flow": "Injector Flow Scaling",
               "fuel.injector_latency": "Injector Latency"}
    out, report = read_semantic_tables(rom, defs, ["TESTREV", "TESTDRIFT"], sem_map)
    # flow: same address in both -> corroborated
    assert report["provenance"]["fuel.injector_flow"].startswith("agree")
    # latency: drifted def reads a non-monotonic axis -> unique plausible survivor wins
    assert report["provenance"]["fuel.injector_latency"] == "plausible-only(TESTREV)"
    assert out["fuel.injector_latency"].values == pytest.approx([2.0, 1.2, 0.7], rel=1e-3)


def test_plausibility_rejects_out_of_bounds():
    sc = Scaling(name="ms", vmin=0.3, vmax=6.0)
    from ecutune.core.models import Table, TableAxis
    good = Table("t", "curve_1d", np.array([2.0, 1.0, 0.5]),
                 x_axis=TableAxis("v", (8.0, 11.0, 14.0)))
    bad_axis = Table("t", "curve_1d", np.array([2.0, 1.0, 0.5]),
                     x_axis=TableAxis("v", (8.0, 14.0, 11.0)))
    bad_vals = Table("t", "curve_1d", np.array([2.0, 9.0, 0.5]),
                     x_axis=TableAxis("v", (8.0, 11.0, 14.0)))
    assert plausible(good, sc)
    assert not plausible(bad_axis, sc)
    assert not plausible(bad_vals, sc)


# ---- integration against the real harvested ROM (skips on fresh clones) ----------------
REPO = Path(__file__).resolve().parents[2]
REAL_ROM = REPO / "ml/data-pipeline/data/raw/roms/romraider/3B12504206_A2WC411D.bin"
REAL_DEFS = REPO / "ml/data-pipeline/data/raw/SubaruDefs/ECUFlash/subaru metric"


@pytest.mark.skipif(not (REAL_ROM.exists() and REAL_DEFS.exists()),
                    reason="harvested ROM / SubaruDefs not present")
def test_real_a2wc411d_read():
    rom = RomImage.load(REAL_ROM)
    defs = EcuFlashDefs(REAL_DEFS)
    out, report = read_semantic_tables(rom, defs, ["A2WC410D", "A2WC412D"],
                                       TO_PLATFORM, VARIANTS)
    assert report["internal_id"] == "A2WC411D"
    assert float(out["fuel.injector_flow"].values) == pytest.approx(503.93, abs=0.05)
    lat = out["fuel.injector_latency"]
    assert np.all(np.diff(lat.values) < 0)          # dead time falls as voltage rises
    idle = out["idle.speed_target_a"]
    assert 600 <= idle.values.min() <= idle.values.max() <= 1800
