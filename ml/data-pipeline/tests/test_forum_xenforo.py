"""forum_xenforo generic engine — parse-level tests on synthetic XenForo 2.x markup."""
from __future__ import annotations

from bs4 import BeautifulSoup

from corpus_pipeline.sources.forum_xenforo import (
    _max_page,
    _posts_from,
    _slug_and_id,
    _thread_links,
    _title_ok,
)

_LISTING = """
<html><body>
<div class="structItem structItem--thread">
  <div class="structItem-title"><a href="/threads/ej20x-swap-idle-tuning.123456/">EJ20X swap idle tuning — trims high</a></div>
</div>
<div class="structItem structItem--thread">
  <div class="structItem-title"><a href="/threads/fs-vf48-turbo.999/">FS: VF48 turbo cheap</a></div>
</div>
<div class="structItem structItem--thread">
  <div class="structItem-title"><a href="/threads/ej20x-swap-idle-tuning.123456/page-3/">EJ20X swap idle tuning — trims high</a></div>
</div>
</body></html>
"""

_THREAD = """
<html><body>
<h1 class="p-title-value">EJ20X swap idle tuning — trims high</h1>
<article class="message message--post" data-author="subie_dan">
  <div class="message-attribution"><time datetime="2023-08-01T12:00:00Z">Aug 1, 2023</time></div>
  <div class="message-body"><div class="bbWrapper">Idle AF learning is +13%. MAF reads low vs speed density.
    <blockquote class="bbCodeBlock--quote">someone else said something</blockquote>
  </div></div>
</article>
<article class="message message--post" data-author="tuner_kate">
  <div class="message-body"><div class="bbWrapper">Rescale the low MAF cells; check injector latency at idle voltage.</div></div>
</article>
<nav class="pageNav"><a href="/threads/ej20x-swap-idle-tuning.123456/page-2">2</a><a href="/threads/ej20x-swap-idle-tuning.123456/page-4">4</a></nav>
</body></html>
"""


def test_slug_and_id():
    assert _slug_and_id("/threads/ej20x-swap-idle-tuning.123456/") == ("ej20x-swap-idle-tuning.123456", "123456")
    assert _slug_and_id("/forums/tuning.95/") is None


def test_thread_links_dedup():
    links = _thread_links(BeautifulSoup(_LISTING, "lxml"))
    assert [t for t, _, _ in links] == ["123456", "999"]     # page-3 dup of 123456 collapsed
    assert links[0][1] == "ej20x-swap-idle-tuning.123456"


def test_posts_from_strips_quotes():
    posts = _posts_from(BeautifulSoup(_THREAD, "lxml"))
    assert len(posts) == 2
    author, date, text = posts[0]
    assert author == "subie_dan"                              # from data-author attr
    assert date == "2023-08-01T12:00:00Z"
    assert "AF learning is +13%" in text
    assert "someone else said something" not in text         # quoted block removed
    assert posts[1][0] == "tuner_kate"


def test_max_page():
    assert _max_page(BeautifulSoup(_THREAD, "lxml")) == 4


def test_title_ok():
    kws = ["tune", "idle", "ej20"]
    rej = ["fs:", "for sale"]
    assert _title_ok("EJ20X swap idle tuning — trims high", kws, rej)
    assert not _title_ok("FS: VF48 turbo cheap", kws, rej)
