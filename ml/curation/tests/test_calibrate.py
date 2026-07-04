from judge import calibrate


def test_freeze_sample_is_idempotent(state, cfg):
    ids1 = calibrate.freeze_sample(state, cfg)
    ids2 = calibrate.freeze_sample(state, cfg)
    assert ids1 == ids2
    assert len(ids1) >= 2                     # both community docs included


def test_blind_subset_deterministic(state, cfg):
    assert calibrate.blind_subset(state, cfg) == calibrate.blind_subset(state, cfg)


def test_agreement_metrics(state, cfg):
    ids = calibrate.freeze_sample(state, cfg)[:2]
    ls = cfg.calibration.set_name
    state.add_label(ids[0], score=5, label_set=ls, rater="adjudicated")
    state.add_label(ids[1], score=2, label_set=ls, rater="adjudicated")
    state.add_label(ids[0], score=4, label_set=ls, rater="claude")
    state.add_label(ids[1], score=4, label_set=ls, rater="claude")   # dangerous: truth 2, rated 4
    ag = calibrate.agreement(state, cfg, label_set=ls, truth_rater="adjudicated",
                             other_rater="claude")
    assert ag.n == 2
    assert ag.within1_pct == 50.0
    assert ag.dangerous == 1
    assert ag.keep_agree_pct == 50.0


def test_spearman_perfect_and_inverse():
    import pytest
    assert calibrate._spearman([1, 2, 3, 4], [1, 2, 3, 4]) == pytest.approx(1.0)
    assert calibrate._spearman([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
