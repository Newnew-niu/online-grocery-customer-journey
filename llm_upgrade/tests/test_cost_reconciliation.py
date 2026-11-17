"""Tests for script 11 (cost reconciliation). Fake run files only: no network."""
import importlib
import json

import pytest

m = importlib.import_module("11_cost_reconciliation")

PRICE = {"input_per_million_usd": 0.10, "output_per_million_usd": 0.50, "verified": False}


def run(sample, prompt, inp, out):
    return {"sample": sample, "prompt": prompt, "model": "claude-haiku-5-5", "date": "2026-11-04",
            "reviews": 100, "input_tokens": inp, "output_tokens": out,
            "cost_usd": (inp * 0.10 + out * 0.50) / 1e6}


def write_runs(tmp_path):
    files = {"llm_run_dev_journey_stage_v2.json": run("dev", "journey_stage_v2", 1000, 100),
             "llm_run_test_journey_stage_v2.json": run("test", "journey_stage_v2", 2000, 200),
             "llm_run_all_journey_stage_v2.json": run("all", "journey_stage_v2", 10000, 1000)}
    for name, r in files.items():
        (tmp_path / name).write_text(json.dumps(r), encoding="utf-8")
    return m.load_runs(tmp_path)


def cfg(actual=None, threshold=5, price=PRICE):
    return {"models": {"claude-haiku-5-5": price}, "variance_threshold_pct": threshold,
            "actual": {"cost_usd": actual, "period": "2026-11-04", "source": ""}}


def test_expected_cost():
    assert m.expected_cost(1_000_000, 1_000_000, PRICE) == pytest.approx(0.60)


def test_full_run_removes_reused_cache_once(tmp_path):
    df = m.new_call_tokens(write_runs(tmp_path)).set_index("run_file")
    row = df.loc["reports/llm_run_all_journey_stage_v2.json"]
    assert row["input_tokens"] == 10000 - 1000 - 2000
    assert row["output_tokens"] == 1000 - 100 - 200


@pytest.mark.parametrize("actual,status", [(None, "NOT ENTERED"), (1.04, "OK"), (1.06, "OVER THRESHOLD"),
                                           (0.94, "OVER THRESHOLD")])
def test_reconcile_status(actual, status):
    assert m.reconcile(1.0, actual, 5)[2] == status


def test_reconcile_variance_numbers():
    v, pct, _ = m.reconcile(2.0, 2.5, 5)
    assert v == pytest.approx(0.5) and pct == pytest.approx(25.0)


def test_build_total_row(tmp_path):
    out = m.build(write_runs(tmp_path), cfg(actual=0.01))
    total = out.iloc[-1]
    assert total["run_file"] == "TOTAL"
    assert total["input_tokens"] == 10000  # 1000 + 2000 + the 7000 new in the full run
    assert total["expected_usd"] == pytest.approx(total["logged_cost_usd"])
    assert total["status"] == "OVER THRESHOLD"
    assert not total["prices_verified"]


def test_build_not_entered_and_price_change(tmp_path):
    price = {**PRICE, "input_per_million_usd": 0.20, "verified": True}
    total = m.build(write_runs(tmp_path), cfg(price=price)).iloc[-1]
    assert total["status"] == "NOT ENTERED"
    assert total["expected_usd"] > total["logged_cost_usd"]
    assert total["prices_verified"]


def test_missing_price_stops(tmp_path):
    with pytest.raises(SystemExit):
        m.build(write_runs(tmp_path), {**cfg(), "models": {}})
