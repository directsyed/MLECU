"""ROM-attachment extraction + cookie loading + rom-id guessing (no live calls)."""
from __future__ import annotations

import json

from bs4 import BeautifulSoup

from corpus_pipeline.rom_harvest import _guess_rom_id, _looks_like_html, load_cookie
from corpus_pipeline.sources.forum_phpbb import attachment_links

# real-shaped phpBB attachment markup (from the RomRaider 05 FXT stock-ROM thread)
_THREAD = """
<html><body>
<div class="postbody">
  <a class="postlink" href="./download/file.php?id=32232&amp;sid=deadbeef">05 FXT 4EAT 3B12504206 31NOV18.srf.zip</a>
  <a href="./download/file.php?id=40001">wrx_stage2_base.hex</a>
  <a href="./download/file.php?id=40002">my_datalog.csv</a>          <!-- not a ROM -->
  <a href="./download/file.php?id=40003">vacation_photos.zip</a>     <!-- archive, no ROM hint -->
  <a href="./download/file.php?avatar=27351_1583667686.jpg">avatar</a> <!-- excluded -->
  <a href="./download/file.php?id=32232">dup same id</a>
</div>
</body></html>
"""


def test_attachment_links_filters_to_roms():
    atts = attachment_links(BeautifulSoup(_THREAD, "lxml"), "https://www.romraider.com/forum")
    ids = {aid for aid, _, _ in atts}
    assert ids == {"32232", "40001"}                       # srf.zip (hinted) + .hex; dup collapsed
    by_id = {aid: (fname, url) for aid, fname, url in atts}
    assert by_id["32232"][0] == "05 FXT 4EAT 3B12504206 31NOV18.srf.zip"
    assert by_id["32232"][1] == "https://www.romraider.com/forum/download/file.php?id=32232"
    # datalog.csv (wrong ext) and vacation_photos.zip (archive, no ROM hint) are excluded
    assert "40002" not in ids and "40003" not in ids


def test_guess_rom_id():
    assert _guess_rom_id("05 FXT 4EAT 3B12504206 31NOV18.srf.zip") == "3B12504206"
    assert _guess_rom_id("random_name.bin") is None


def test_looks_like_html_detects_login_redirect():
    assert _looks_like_html(b"<!DOCTYPE html PUBLIC ...")   # 403 login page
    assert not _looks_like_html(b"\x00\x01\x02\x03rombytes")  # real binary


def test_load_cookie_json_and_raw(tmp_path):
    j = tmp_path / "romraider.json"
    j.write_text(json.dumps({"phpbb3_x_sid": "abc", "phpbb3_x_u": "42"}))

    class _Cfg:
        def resolve(self, p):
            return j
    assert load_cookie(_Cfg(), "ignored").replace(" ", "") == "phpbb3_x_sid=abc;phpbb3_x_u=42"
