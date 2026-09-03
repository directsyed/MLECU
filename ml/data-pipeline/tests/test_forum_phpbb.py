"""forum_phpbb generic engine, parse-level tests on synthetic prosilver/subsilver markup."""
from __future__ import annotations

from bs4 import BeautifulSoup

from corpus_pipeline.sources.forum_phpbb import (
    _page_starts,
    _posts_from,
    _strip_sid,
    _title_ok,
    _topic_links,
)

_VIEWFORUM = """
<html><body>
<a class="topictitle" href="./viewtopic.php?f=15&t=15258&sid=abc123def456">2005 Forester XT 4EAT stock ROM map</a>
<a class="topictitle" href="./viewtopic.php?f=15&t=999">FS: VF48 turbo, cheap</a>
<a class="topictitle" href="./viewtopic.php?f=15&t=15258&sid=aa">duplicate same thread</a>
<a class="topictitle" href="https://www.romraider.com/forum/viewtopic.php?f=51&t=777">Idle tuning: MAF vs speed density</a>
</body></html>
"""

_VIEWTOPIC = """
<html><body>
<h2 class="topic-title"><a href="#">Idle tuning: MAF vs speed density</a></h2>
<div class="post bg1">
  <p class="author"><a class="username" href="#">tuner_bob</a><time datetime="2024-05-01T10:00:00Z">May 1</time></p>
  <div class="content">My trims are +12% at idle.\nMAF reads 2.1 g/s.</div>
</div>
<div class="post bg2">
  <p class="author"><span class="username-coloured">mod_alice</span></p>
  <div class="content">Check injector latency first, voltage dependent.</div>
</div>
<div class="pagination"><a href="./viewtopic.php?t=777&start=10">2</a><a href="./viewtopic.php?t=777&start=20">3</a></div>
</body></html>
"""


def test_strip_sid():
    assert "sid=" not in _strip_sid("./viewtopic.php?f=1&t=2&sid=0a1b2c")


def test_topic_links_dedup_and_absolute():
    links = _topic_links(BeautifulSoup(_VIEWFORUM, "lxml"), "https://www.romraider.com/forum")
    ids = [t for t, _, _ in links]
    assert ids == ["15258", "999", "777"]          # duplicate t=15258 collapsed
    assert all(u.startswith("https://") for _, _, u in links)


def test_posts_from_prosilver():
    posts = _posts_from(BeautifulSoup(_VIEWTOPIC, "lxml"))
    assert len(posts) == 2
    author, date, text = posts[0]
    assert author == "tuner_bob"
    assert date == "2024-05-01T10:00:00Z"
    assert "trims are +12%" in text
    assert posts[1][0] == "mod_alice"


def test_page_starts():
    assert _page_starts(BeautifulSoup(_VIEWTOPIC, "lxml")) == [0, 10, 20]


def test_title_ok_keywords_and_reject():
    kws = ["tune", "rom", "idle"]
    rej = ["for sale", "fs:"]
    assert _title_ok("2005 Forester XT 4EAT stock ROM map", kws, rej)
    assert not _title_ok("FS: VF48 turbo, cheap", kws, rej)      # reject wins
    assert not _title_ok("What wheels fit?", kws, rej)           # no keyword
    assert _title_ok("anything", [], rej)                        # empty keywords = allow
