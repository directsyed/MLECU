"""Pure-parser tests for the legacygt source (no browser/network)."""
from bs4 import BeautifulSoup

from corpus_pipeline.sources.forum_legacygt import _max_page, _posts_from, _thread_id

HTML = """<html><body>
<h1>EJ20X Base Map</h1>
<div class="ipsPagination">
  <a href="/topic/131452-x/page/2/">2</a><a href="/topic/131452-x/page/3/">3</a>
</div>
<article id="elComment_1"><div class="cAuthorPane_author"><a>captainobvious</a></div>
  <time datetime="2020-01-24T18:01:00Z"></time>
  <div class="ipsType_richText">Looking for a base map for my ej20x swap.</div></article>
<article id="elComment_2"><div class="cAuthorPane_author"><a>tuner2</a></div>
  <time datetime="2020-01-25T10:00:00Z"></time>
  <div class="ipsType_richText">Use the USDM EJ255 tune, runs fine.</div></article>
</body></html>"""


def test_thread_id():
    assert _thread_id("https://www.legacygt.com/topic/131452-ej20x-base-map-after-swap/") == "131452"


def test_max_page():
    assert _max_page(BeautifulSoup(HTML, "lxml")) == 3


def test_posts_from():
    posts = _posts_from(BeautifulSoup(HTML, "lxml"))
    assert len(posts) == 2
    assert posts[0][0] == "captainobvious" and posts[0][1] == "2020-01-24T18:01:00Z"
    assert "base map" in posts[0][2].lower()
