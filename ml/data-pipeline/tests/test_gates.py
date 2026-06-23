from corpus_pipeline.core.config import GatesCfg
from corpus_pipeline.core.gates import evaluate
from corpus_pipeline.core.models import Document

G = GatesCfg()


def _doc(text, **kw):
    return Document(source="t", source_id="1", title=kw.pop("title", "t"), text=text, **kw)


def test_rejects_too_short():
    kept, reason, _ = evaluate(_doc("tiny"), G)
    assert not kept and reason == "too_short"


def test_rejects_no_alpha():
    kept, reason, _ = evaluate(_doc("12345 67890 " * 5), G)
    assert not kept and reason == "no_alpha"


def test_keeps_ecu_definition_and_flags():
    text = "Subaru Forester ECU\nTunable tables (3):\n  - Primary Open Loop Fueling\n  - Boost Target"
    kept, reason, flags = evaluate(_doc(text, kind="ecu_definition", domain="subaru"), G)
    assert kept and reason is None
    assert "has_table" in flags        # kind=ecu_definition implies tabular
    assert "tuning_signal" in flags    # 'fueling'/'boost'
    assert "has_numbers" in flags      # the '(3)'
    assert "subaru" in flags


def test_tuning_signal_on_prose():
    kept, _, flags = evaluate(_doc("Adjust the injector latency and watch the AFR under boost."), G)
    assert kept and "tuning_signal" in flags
