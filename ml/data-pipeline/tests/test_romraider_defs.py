"""Parser test against a real cloned ECUFlash def (skips if the repo isn't present)."""
from pathlib import Path

import pytest
from lxml import etree

from corpus_pipeline.core.config import REPO_ROOT
from corpus_pipeline.sources.romraider_defs import _parse_rom

SAMPLE = REPO_ROOT / "data/raw/SubaruDefs/ECUFlash/subaru standard/Forester 2.5/E2UE102J.xml"


@pytest.mark.skipif(not SAMPLE.exists(), reason="SubaruDefs not cloned")
def test_parse_rom_extracts_identity_and_tables():
    base = REPO_ROOT / "data/raw/SubaruDefs"
    doc = _parse_rom(SAMPLE, base, etree.XMLParser(recover=True))
    assert doc is not None
    assert doc.source == "romraider_defs"
    assert doc.source_id == "E2UE102J"
    assert doc.kind == "ecu_definition" and doc.domain == "subaru"
    assert doc.meta["model"] == "Forester"
    assert doc.meta["memmodel"] == "SH7058"
    assert doc.meta["table_count"] > 50          # this ROM has hundreds of tables
    assert "Primary Open Loop Fueling" in doc.text
    assert doc.url.endswith("E2UE102J.xml")
    assert doc.content_hash and doc.token_est > 0


def test_base_def_without_romid_is_skipped(tmp_path: Path):
    p = tmp_path / "base.xml"
    p.write_text('<rom><include>32BITBASE</include><table name="X" address="1"/></rom>')
    assert _parse_rom(p, tmp_path, etree.XMLParser(recover=True)) is None
