"""Tests for script 10 (vendor scorecard). Synthetic numbers only: no network, no reviews."""
import importlib

import pandas as pd
import pytest

m = importlib.import_module("10_vendor_scorecard")

WEIGHTS = {"quality": 40, "consistency": 15, "efficiency": 15, "cost": 15, "reliability": 15}


def raw(f1_rules=0.6, f1_llm=0.7):
    return {
        "rules": {"micro_f1": f1_rules, "kappa_vs_person": 0.5, "reviews_per_minute": 1000.0,
                  "cost_per_1000_usd": 0.0,
                  "rates": {"failure_rate": 0.0, "inexact_quote_rate": None, "repeat_run_change_rate": 0.0}},
        "llm": {"micro_f1": f1_llm, "kappa_vs_person": -0.1, "reviews_per_minute": 50.0,
                "cost_per_1000_usd": 0.2,
                "rates": {"failure_rate": 0.0, "inexact_quote_rate": 0.0, "repeat_run_change_rate": 0.12}},
    }


def diffs(all_diff=(0.6, 0.7, 0.01, 0.12), first=(0.7, 0.65), rest=(0.6, 0.72)):
    rows = [{"label_round": "all100", "reviews": 100, "f1_rules": all_diff[0], "f1_llm": all_diff[1],
             "ci_low": all_diff[2], "ci_high": all_diff[3],
             "ci_excludes_zero": all_diff[2] > 0 or all_diff[3] < 0}]
    for name, n, (a, b) in (("first30", 30, first), ("rest70", 70, rest)):
        rows.append({"label_round": name, "reviews": n, "f1_rules": a, "f1_llm": b,
                     "ci_low": -1, "ci_high": 1, "ci_excludes_zero": False})
    return pd.DataFrame(rows)


def test_codes_parsing():
    assert m.codes("AP;PL") == ["AP", "PL"]
    assert m.codes("") == [] and m.codes(float("nan")) == []


def test_relative_scores():
    assert m.relative_higher_better({"a": 50, "b": 100}) == {"a": 50.0, "b": 100.0}
    assert m.relative_lower_better({"a": 0.0, "b": 0.2}) == {"a": 100.0, "b": 0.0}
    assert m.relative_lower_better({"a": 1.0, "b": 2.0}) == {"a": 100.0, "b": 50.0}


def test_reliability_skips_not_applicable_rates():
    assert m.reliability_score({"x": 0.0, "y": None}) == 100.0
    assert m.reliability_score({"x": 0.1, "y": 0.5}) == pytest.approx(45.0)


def test_dimension_scores_and_kappa_floor():
    s = m.dimension_scores(raw())
    assert s["rules"]["quality"] == pytest.approx(60)
    assert s["llm"]["consistency"] == 0.0  # negative kappa is floored at 0
    assert s["llm"]["efficiency"] == pytest.approx(5.0)
    assert s["llm"]["reliability"] == pytest.approx(88.0)


def test_overall_normalises_weights():
    scores = {d: 50.0 for d in m.DIMENSIONS}
    assert m.overall(scores, WEIGHTS) == pytest.approx(50.0)
    assert m.overall(scores, {d: w * 3 for d, w in WEIGHTS.items()}) == pytest.approx(50.0)


def test_sensitivity_rows_and_random_shares():
    s = m.dimension_scores(raw())
    table, share = m.sensitivity(s, WEIGHTS, draws=200, seed=1)
    assert sum(share.values()) == pytest.approx(1.0)
    q = table.set_index("scenario").loc["quality only"]
    assert q["winner"] == "llm"
    assert "without cost" in set(table["scenario"])


def test_recommendation_follows_weighted_score_when_gap_is_noise():
    totals = {"rules": 80, "llm": 50}
    d = diffs(all_diff=(0.65, 0.70, -0.02, 0.12))
    vendor, text = m.recommendation(totals, d, 0.22, 0.12, {"rules": 0.99})
    assert vendor == "rules"
    assert "within noise" in text


def test_recommendation_flags_conflict_and_unstable_rounds():
    totals = {"rules": 80, "llm": 50}
    vendor, text = m.recommendation(totals, diffs(), 0.22, 0.12, {"rules": 0.99})
    assert vendor == "llm"
    assert "not stable across the two labelling rounds" in text
    assert "within noise" not in text


def test_recommendation_no_round_warning_when_rounds_agree():
    totals = {"rules": 80, "llm": 50}
    _, text = m.recommendation(totals, diffs(first=(0.6, 0.7)), 0.22, 0.12, {"rules": 0.99})
    assert "not stable" not in text


def test_md_table():
    t = m.md_table(pd.DataFrame({"a": [1], "b": ["x"]}))
    assert t.splitlines() == ["| a | b |", "|---|---|", "| 1 | x |"]
