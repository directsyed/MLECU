"""forum_nasioc — parse-level tests on synthetic vBulletin 3.x markup."""
from __future__ import annotations

from bs4 import BeautifulSoup

from corpus_pipeline.sources.forum_nasioc import _max_page, _posts_from, _thread_links

_FORUMDISPLAY = """
<html><body>
<a id="thread_title_2882357" href="showthread.php?t=2882357">05 Forester XT build help</a>
<a id="thread_title_111" href="showthread.php?t=111">FS: cobb accessport v3</a>
<a id="thread_title_222" href="https://forums.nasioc.com/forums/showthread.php?t=222">Knock correction on 93 octane — datalog inside</a>
</body></html>
"""

_SHOWTHREAD = """
<html><body>
<td class="navbar"><strong>05 Forester XT build help</strong></td>
<table class="tborder" id="post100">
  <tr><td><a class="bigusername" href="#">subie_dan</a></td></tr>
  <tr><td><div id="post_message_100">Swapped an EJ20X in. Idle hunts when warm.\nTrims at +14%.</div></td></tr>
</table>
<table class="tborder" id="post101">
  <tr><td><a class="bigusername" href="#">fxt_mike</a></td></tr>
  <tr><td><div id="post_message_101">Smoke test the intake first — TGV delete gaskets leak.</div></td></tr>
</table>
<div class="pagenav"><a href="showthread.php?t=2882357&page=2">2</a><a href="showthread.php?t=2882357&page=5">5</a></div>
</body></html>
"""


def test_thread_links():
    links = _thread_links(BeautifulSoup(_FORUMDISPLAY, "lxml"), "https://forums.nasioc.com/forums")
    assert [t for t, _, _ in links] == ["2882357", "111", "222"]
    assert links[0][1] == "05 Forester XT build help"
    assert all(u.startswith("https://") for _, _, u in links)


def test_posts_from_vb3():
    posts = _posts_from(BeautifulSoup(_SHOWTHREAD, "lxml"))
    assert len(posts) == 2
    assert posts[0][0] == "subie_dan"
    assert "Trims at +14%" in posts[0][2]
    assert posts[1][0] == "fxt_mike"


def test_max_page():
    assert _max_page(BeautifulSoup(_SHOWTHREAD, "lxml")) == 5
