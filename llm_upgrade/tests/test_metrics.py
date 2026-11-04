import numpy as np
import pytest

from eval_metrics import bootstrap_ci, cohen_kappa, macro, micro, per_stage

TRUTH = np.array([[1, 0], [1, 1], [0, 0], [0, 1]])
PRED = np.array([[1, 0], [0, 1], [1, 0], [0, 0]])


def test_micro_counts_match_script_03_definitions():
    # tp=2, fp=1, fn=2
    s = micro(TRUTH, PRED)
    assert s["precision"] == pytest.approx(2 / 3)
    assert s["recall"] == pytest.approx(0.5)
    assert s["f1"] == pytest.approx(4 / 7)


def test_macro_averages_each_stage():
    s = macro(TRUTH, PRED)
    assert s["precision"] == pytest.approx((0.5 + 1.0) / 2)
    assert s["recall"] == pytest.approx(0.5)


def test_no_predictions_gives_none_precision_not_zero():
    pred = np.zeros_like(TRUTH)
    st = per_stage(TRUTH, pred, ["AA", "BB"])
    assert st["AA"]["precision"] is None
    assert st["AA"]["recall"] == 0
    assert macro(TRUTH, pred)["precision"] is None


def test_macro_skips_undefined_stage():
    truth = np.array([[1, 0], [1, 0]])
    pred = np.array([[1, 0], [1, 0]])
    assert macro(truth, pred)["f1"] == 1.0  # second stage has no cases at all


def test_bootstrap_identical_methods_have_zero_difference():
    out = bootstrap_ci(TRUTH, {"a": PRED, "b": PRED.copy()}, n_boot=50)
    assert out["b"]["diff_vs_a"]["f1"] == [0.0, 0.0]


def test_kappa_perfect_and_chance():
    assert cohen_kappa(TRUTH, TRUTH) == 1.0
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0.0)
