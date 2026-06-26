from corpus_pipeline.sources.ecu_docs import _clean

HTML = """<html><head><title>How EFI Works</title><style>.x{color:red}</style></head>
<body><script>var secret=1;</script>
<h1>Fuel Equation</h1>
<p>PW = REQ_FUEL * VE * MAP * E + accel + injector_open_time</p>
<p>VE is volumetric efficiency.</p></body></html>"""


def test_clean_strips_script_style_and_extracts_text():
    title, text = _clean(HTML)
    assert title == "How EFI Works"
    assert "secret" not in text          # <script> removed
    assert "color:red" not in text       # <style> removed
    assert "REQ_FUEL" in text and "volumetric efficiency" in text
