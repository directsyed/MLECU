from judge.chunker import Chunk, aggregate, chunk


def test_short_doc_untouched():
    out = chunk("hello world", max_chars=100)
    assert out == [Chunk(0, 1, "hello world")]


def test_long_doc_splits_on_paragraphs():
    text = "\n\n".join(f"paragraph {i} " + "x" * 80 for i in range(40))
    out = chunk(text, max_chars=1000, overlap_chars=100)
    assert len(out) > 1
    assert all(len(c.text) <= 1100 for c in out)          # max + overlap slack
    assert all(c.n_chunks == len(out) for c in out)
    # overlap: the head of chunk N repeats the tail of chunk N-1
    assert out[1].text[:50] in out[0].text


def test_pathological_single_paragraph():
    out = chunk("y" * 5000, max_chars=1000, overlap_chars=0)
    assert len(out) == 5
    assert "".join(c.text for c in out) == "y" * 5000


def test_aggregate_modes():
    assert aggregate([5, 3, 4], [10, 10, 10], "min") == 3
    assert aggregate([5, 3, 4], [10, 10, 10], "mean") == 4
    assert aggregate([5, 1], [1000, 10], "weighted_mean") == 5
