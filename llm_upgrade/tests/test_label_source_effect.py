"""Tests for script 13 (label source effect). Synthetic labels only: no network, no reviews."""
import importlib

import pandas as pd
import pytest

m = importlib.import_module("13_label_source_effect")


def frame():
    return pd.DataFrame({
        "label_round": ["first30", "first30", "rest70", "rest70"],
        "ai":     [["AP"], ["PL"], ["AL"], ["CP"]],
        "person": [["AP"], [],     ["AL"], ["SB"]],
        "rules":  [["AP"], ["PL"], [],     ["CP"]],
        "llm":    [["AP"], [],     ["AL"], ["SB"]],
    })


def test_groups_vendors_and_paired_reviews():
    out = m.score_table(frame())
    assert len(out) == 6
    assert out.set_index(["group", "vendor"]).loc[("all100", "rules"), "reviews"] == 4
    assert out.set_index(["group", "vendor"]).loc[("first30", "llm"), "reviews"] == 2


def test_scores_and_change():
    r = m.score_table(frame()).set_index(["group", "vendor"]).loc[("all100", "rules")]
    # vs AI labels: rules get AP, PL, CP right and miss AL
    assert r["ai_precision"] == pytest.approx(1.0) and r["ai_recall"] == pytest.approx(0.75)
    # vs person: AP right; PL and CP wrong; AL and SB missed
    assert r["person_precision"] == pytest.approx(1 / 3) and r["person_recall"] == pytest.approx(1 / 3)
    assert r["precision_change_person_minus_ai"] == pytest.approx(1 / 3 - 1.0)
    assert (r["ai_tp"], r["ai_fp"], r["ai_fn"]) == (3, 0, 1)
