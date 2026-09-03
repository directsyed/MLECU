"""tunerstudio_ini, parser tests on a synthetic speeduino.ini fragment."""
from __future__ import annotations

from corpus_pipeline.sources.tunerstudio_ini import _parse_ini

_INI = """
[Constants]
   reqFuel = scalar, U08, 0, "ms", 0.1, 0.0, 0.0, 25.5, 1

[TableEditor]
   table = veTable1Tbl, veTable1Map, "VE Table", 2
      topicHelp = "https://wiki.speeduino.com/en/configuration/VE_Table"
      xBins = rpmBins, rpm
      yBins = fuelLoadBins, fuelLoad
      zBins = veTable

   table = advTable1Tbl, advTable1Map, "Ignition Advance Table", 3
      xBins = rpmBins2, rpm
      yBins = ignLoadBins, ignLoad
      zBins = advTable1

[CurveEditor]
   curve = warmup_curve, "Warmup Enrichment (WUE) Curve"
      columnLabel = "Coolant", "WUE %"
      xBins = wueBins, coolant
      yBins = wueRates

[SettingContextHelp]
   nothing = "here"
"""


def test_parse_ini_tables_and_curves():
    docs = list(_parse_ini(_INI, "https://example/ini"))
    ids = [d.source_id for d in docs]
    assert ids == ["table:veTable1Tbl", "table:advTable1Tbl", "curve:warmup_curve"]

    ve = docs[0]
    assert ve.title == "Speeduino table: VE Table"
    assert ve.kind == "ecu_definition"
    assert ve.tier == "reference"
    assert ve.domain == "general"
    assert ve.meta["xBins"].startswith("rpmBins")
    assert "zBins = veTable" in ve.text

    wue = docs[2]
    assert wue.title == "Speeduino curve: Warmup Enrichment (WUE) Curve"
    assert wue.meta["ini_name"] == "warmup_curve"


def test_parse_ini_ignores_other_sections():
    docs = list(_parse_ini("[Constants]\n reqFuel = scalar\n[PcVariables]\n x = 1\n", "u"))
    assert docs == []
