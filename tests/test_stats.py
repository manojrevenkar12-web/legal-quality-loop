import pytest

from qloop.stats import cohen_kappa, holm, items_needed, mcnemar, paired_difference, tied_groups, wilson


def test_wilson():
    w = wilson(8, 10)
    assert w.low == pytest.approx(0.4902, abs=1e-3) and w.high == pytest.approx(0.9433, abs=1e-3)
    assert wilson(0, 0).high == 1.0


def test_kappa():
    assert cohen_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohen_kappa([True, True, False, False], [True, False, True, False]) == pytest.approx(0.0)


def test_paired_difference_and_mcnemar():
    a = [1.0] * 50 + [0.0] * 50
    assert paired_difference(a, a, 500, 0.05).contains(0.0)
    b = [1.0] * 80 + [0.0] * 20
    assert paired_difference(a, b, 500, 0.05).low > 0
    assert mcnemar([x > 0 for x in a], [x > 0 for x in b]) < 0.001


def test_holm_and_sample_size():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert 600 < items_needed(0.85, 0.05) < 1000


def test_tied_groups():
    scores = {"a": [1.0] * 90 + [0.0] * 10, "b": [1.0] * 88 + [0.0] * 12, "c": [1.0] * 40 + [0.0] * 60}
    assert tied_groups(["a", "b", "c"], scores, 500, 0.05) == [["a", "b"], ["c"]]
