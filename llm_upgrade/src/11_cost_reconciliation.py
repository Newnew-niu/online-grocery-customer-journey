"""Step 11: Cost reconciliation. Compare the expected API cost with the actual bill.

expected = logged input and output tokens x unit prices in config/pricing.yaml
actual   = a figure the owner enters by hand in config/pricing.yaml, from the Anthropic console

One row per LLM run, then a TOTAL row. The full run ("all") reused the cached
answers of the dev v2 and test v2 runs, so their tokens are taken out of it once,
as in script 07c. Only the TOTAL row has an actual figure, because the console does
not split the bill by run.

Columns:
- logged_cost_usd: the cost written by script 06 at run time (prices in src/llm_client.py)
- expected_usd:    tokens x the prices in config/pricing.yaml
- status:          NOT ENTERED (no actual yet), OK, or OVER THRESHOLD

Inputs:  reports/llm_run_*.json, config/pricing.yaml
Output:  reports/cost_reconciliation.csv
No API calls.
"""
import json

import pandas as pd

from common import REPORTS, UPGRADE

CONFIG = UPGRADE / "config" / "pricing.yaml"
FROZEN = "journey_stage_v2"


def load_runs(reports=REPORTS):
    runs = {}
    for p in sorted(reports.glob("llm_run_*.json")):
        runs[p.name] = json.loads(p.read_text(encoding="utf-8"))
    return runs


def new_call_tokens(runs, frozen=FROZEN):
    """Tokens per run that were new API calls. The full run's reused cache hits are removed."""
    rows = []
    reused = [f"llm_run_dev_{frozen}.json", f"llm_run_test_{frozen}.json"]
    for name, r in runs.items():
        inp, out, cost = r["input_tokens"], r["output_tokens"], r["cost_usd"]
        note = ""
        if name == f"llm_run_all_{frozen}.json":
            for k in reused:
                inp -= runs[k]["input_tokens"]
                out -= runs[k]["output_tokens"]
                cost -= runs[k]["cost_usd"]
            note = "minus the cached dev and test answers it reused"
        rows.append({"run_file": f"reports/{name}", "sample": r["sample"], "prompt": r["prompt"],
                     "model": r["model"], "date": r["date"], "reviews": r["reviews"],
                     "input_tokens": inp, "output_tokens": out, "logged_cost_usd": cost, "note": note})
    return pd.DataFrame(rows)


def expected_cost(input_tokens, output_tokens, price):
    return (input_tokens * price["input_per_million_usd"]
            + output_tokens * price["output_per_million_usd"]) / 1_000_000


def reconcile(expected, actual, threshold_pct):
    """Return (variance_usd, variance_pct, status)."""
    if actual is None:
        return None, None, "NOT ENTERED"
    variance = actual - expected
    pct = 100 * variance / expected if expected else None
    over = pct is None or abs(pct) > threshold_pct
    return variance, pct, "OVER THRESHOLD" if over else "OK"


def build(runs, cfg):
    df = new_call_tokens(runs)
    prices = cfg["models"]
    missing = sorted(set(df["model"]) - set(prices))
    if missing:
        raise SystemExit(f"No price in config/pricing.yaml for {missing}")
    df["input_price_per_million_usd"] = df["model"].map(lambda m: prices[m]["input_per_million_usd"])
    df["output_price_per_million_usd"] = df["model"].map(lambda m: prices[m]["output_per_million_usd"])
    df["prices_verified"] = df["model"].map(lambda m: bool(prices[m].get("verified")))
    df["expected_usd"] = [expected_cost(i, o, prices[m]) for i, o, m in
                          zip(df["input_tokens"], df["output_tokens"], df["model"])]
    actual = cfg["actual"]["cost_usd"]
    threshold = cfg["variance_threshold_pct"]
    variance, pct, status = reconcile(df["expected_usd"].sum(), actual, threshold)
    total = {"run_file": "TOTAL", "sample": "", "prompt": "", "model": "", "date": cfg["actual"]["period"],
             "reviews": "", "input_tokens": df["input_tokens"].sum(), "output_tokens": df["output_tokens"].sum(),
             "logged_cost_usd": df["logged_cost_usd"].sum(), "note": cfg["actual"].get("source", ""),
             "input_price_per_million_usd": "", "output_price_per_million_usd": "",
             "prices_verified": bool(df["prices_verified"].all()),
             "expected_usd": df["expected_usd"].sum(), "actual_usd": actual,
             "variance_usd": variance, "variance_pct": pct, "threshold_pct": threshold, "status": status}
    for col in ("actual_usd", "variance_usd", "variance_pct", "threshold_pct"):
        df[col] = ""  # empty: the console bill is not split by run
    df["status"] = "per-run actual NOT AVAILABLE (console does not split by run)"
    return pd.DataFrame(df.to_dict("records") + [total])


def main():
    import yaml  # imported here so the tests need no PyYAML

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    out = build(load_runs(), cfg)
    out.to_csv(REPORTS / "cost_reconciliation.csv", index=False)
    t = out.iloc[-1]
    print(out[["run_file", "input_tokens", "output_tokens", "logged_cost_usd", "expected_usd"]].to_string(index=False))
    print(f"\nExpected ${t['expected_usd']:.4f} | actual {t['actual_usd']} | status {t['status']}"
          f" | prices verified: {t['prices_verified']}")
    if not t["prices_verified"]:
        print("VERIFY: prices in config/pricing.yaml are not checked yet.")


if __name__ == "__main__":
    main()
