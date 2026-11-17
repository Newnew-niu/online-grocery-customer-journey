"""Tests for script 12 (simulated daily SLA). Synthetic data only: no network, no reviews."""
import importlib

import pandas as pd
import pytest

m = importlib.import_module("12_simulated_daily_sla")

T = {"min_output_volume": 3, "max_failure_rate": 0.005, "max_retry_rate": 0.01, "max_quote_fail_rate": 0.01,
     "max_disagreement_rate": 0.4, "max_cost_per_1000_usd": 0.3, "min_qa_sample": 2, "min_qa_f1": 0.6}
CFG = {"simulation": {"batches": 2, "seed": 1, "first_batch_date": "2026-11-09", "qa_sample_per_batch": 10},
       "thresholds": T, "owners": {"rules": "R owner", "llm": "L owner"}}
PRICES = {"input_per_million_usd": 0.10, "output_per_million_usd": 0.50}


def test_assign_batches_is_repeatable_and_complete():
    ids = [f"r{i}" for i in range(10)]
    a = m.assign_batches(ids, 3, seed=7, first_date="2026-11-09")
    b = m.assign_batches(ids, 3, seed=7, first_date="2026-11-09")
    pd.testing.assert_frame_equal(a, b)
    assert sorted(a["review_id"]) == sorted(ids)
    assert a["sim_batch_id"].value_counts().sort_index().tolist() == [4, 3, 3]
    assert sorted(a["sim_batch_date"].unique()) == ["2026-11-09", "2026-11-10", "2026-11-11"]


def test_qa_sample_uses_only_labelled_reviews_and_caps_size():
    batch = pd.DataFrame({"person_labels": [["AP"], None, [], ["PL"], None]})
    assert len(m.qa_sample(batch, 10, seed=1)) == 3
    s = m.qa_sample(batch, 2, seed=1)
    assert len(s) == 2 and s["person_labels"].notna().all()


def test_qa_scores_empty_sample():
    assert m.qa_scores(pd.DataFrame({"person_labels": [], "llm_labels": []}), "llm")["f1"] is None


def test_check_breach_skips_not_applicable_and_lists_reasons():
    row = {"output_volume": 5, "failure_rate": 0.0, "retry_rate": 0.02, "quote_fail_rate": None,
           "disagreement_rate": float("nan"), "cost_per_1000_usd": 0.0, "qa_sample_size": 1, "qa_f1": None}
    breach, reasons = m.check_breach(row, T)
    assert breach
    assert "retry rate above" in reasons and "QA sample below" in reasons
    assert "quote" not in reasons and "disagreement" not in reasons


def test_check_breach_ok():
    row = {"output_volume": 5, "failure_rate": 0.0, "retry_rate": 0.0, "quote_fail_rate": 0.0,
           "disagreement_rate": 0.1, "cost_per_1000_usd": 0.2, "qa_sample_size": 3, "qa_f1": 0.9}
    assert m.check_breach(row, T) == (False, "")


def reviews():
    return pd.DataFrame({
        "review_id": ["a", "b", "c", "d"],
        "sim_batch_id": ["SIM-B01"] * 4, "sim_batch_date": ["2026-11-09"] * 4,
        "rules_labels": [["AP"], ["PL"], [], ["AL"]],
        "llm_labels": [["AP"], ["PL", "AL"], [], ["AL"]],
        "person_labels": [["AP"], ["PL"], [], None],
        "llm_ok": [True, True, True, True], "attempts": [1, 2, 1, 1],
        "input_tokens": [1_000_000, 0, 0, 0], "output_tokens": [0, 0, 0, 0],
        "quotes": [1, 2, 0, 1], "quotes_exact": [1, 1, 0, 1],
    })


def test_batch_rows_metrics_and_breach():
    rows = m.batch_rows(reviews(), CFG, PRICES).set_index("vendor")
    llm, rules = rows.loc["llm"], rows.loc["rules"]
    assert llm["output_volume"] == 4
    assert llm["disagreement_rate"] == pytest.approx(0.25) == rules["disagreement_rate"]
    assert llm["retry_rate"] == pytest.approx(0.25)
    assert llm["quote_fail_rate"] == pytest.approx(0.25)
    assert llm["cost_usd"] == pytest.approx(0.10)
    assert llm["cost_per_1000_usd"] == pytest.approx(25.0)
    assert llm["qa_sample_size"] == 3 and llm["person_labelled_in_batch"] == 3
    assert rules["qa_f1"] == pytest.approx(1.0)
    assert pd.isna(rules["quote_fail_rate"]) and rules["cost_usd"] == 0.0  # not applicable: blank
    assert llm["breach"] == "TRUE" and "cost per 1,000" in llm["breach_reason"]
    assert rules["breach"] == "FALSE" and rules["sim_status"] == "No action"
