import pytest

from judge.verdict import VerdictError, parse


def test_parses_clean_json():
    v = parse('{"score": 4, "rationale": "solid", "pairs": [], "claims_checked": []}')
    assert v.score == 4 and v.rationale == "solid" and v.pairs == []


def test_strips_code_fences():
    v = parse('```json\n{"score": 5, "rationale": "ok", "pairs": [], "claims_checked": []}\n```')
    assert v.score == 5


@pytest.mark.parametrize("bad", [
    "not json",
    '{"score": 9, "rationale": "x", "pairs": [], "claims_checked": []}',
    '{"score": 3, "rationale": "", "pairs": [], "claims_checked": []}',
    '{"score": 3, "rationale": "x", "pairs": [{"symptoms": "s"}], "claims_checked": []}',
])
def test_rejects_invalid(bad):
    with pytest.raises(VerdictError):
        parse(bad)
