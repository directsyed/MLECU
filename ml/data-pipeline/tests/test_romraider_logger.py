from lxml import etree

from corpus_pipeline.sources.romraider_logger import _ecuparam_doc, _param_doc


def test_param_doc():
    el = etree.fromstring(
        '<parameter id="P23" name="Knock Correction Advance" desc="" ecubyteindex="8" ecubit="1">'
        '<address>0x000022</address><conversions>'
        '<conversion units="degrees" expr="(x-128)/2" format="0.00"/></conversions></parameter>'
    )
    d = _param_doc(el)
    assert d.source == "romraider_logger" and d.source_id == "P23"
    assert d.kind == "logger_param" and d.domain == "subaru"
    assert d.meta["units"] == ["degrees"]
    assert "Knock Correction Advance" in d.title and "0x000022" in d.text


def test_ecuparam_doc_counts_ecus():
    el = etree.fromstring(
        '<ecuparam id="E1" name="Fine Knock Learn" desc="x">'
        '<ecu id="a"><address>0x1</address></ecu><ecu id="b"><address>0x2</address></ecu>'
        '<conversions><conversion units="degrees" expr="x"/></conversions></ecuparam>'
    )
    d = _ecuparam_doc(el)
    assert d.source_id == "E1" and d.meta["supported_ecu_count"] == 2
    assert "degrees" in d.meta["units"]
