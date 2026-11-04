"""Step 7c: Write the summary numbers used in the Module 5 report.

- API spend across all runs. The full run reuses cached dev and test answers, so
  those are taken out once to avoid counting them twice.
- Point differences in F1, and which method is closer to the labels when they differ.
- Micro scores on the person's labels without the RS stage.
- How close the LLM pain-point ranking is to the rule-based one.

Output: reports/llm_summary.json
"""
import json

import pandas as pd

from common import REPORTS


def load(name):
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def codes(value):
    return {c for c in str(value).split(";") if c and c != "nan"}


def api_spend(prompt):
    dev = [load(f.name) for f in sorted(REPORTS.glob("llm_run_dev_*.json"))]
    test, full = load(f"llm_run_test_{prompt}.json"), load(f"llm_run_all_{prompt}.json")
    reused = load(f"llm_run_dev_{prompt}.json")["cost_usd"] + test["cost_usd"]
    total = sum(r["cost_usd"] for r in dev) + test["cost_usd"] + full["cost_usd"] - reused
    return {
        "dev_prompt_work_usd": sum(r["cost_usd"] for r in dev), "test_usd": test["cost_usd"],
        "full_run_new_calls_usd": full["cost_usd"] - reused, "total_usd": total,
        "full_run_reviews": full["reviews"], "full_run_failures": full["failures"],
        "full_run_retries": full["retries"], "full_run_valid_quote_rate": full["valid_quote_rate"],
        "full_run_tokens": full["input_tokens"] + full["output_tokens"],
    }


def micro_without(table, stage):
    t = table[(table["method"].isin(["rules", "llm"])) & (table["level"] != stage)
              & (~table["level"].str.startswith("ALL"))]
    out = {}
    for m, g in t.groupby("method"):
        tp, fp, fn = g["tp"].sum(), g["fp"].sum(), g["fn"].sum()
        out[m] = {"tp": int(tp), "fp": int(fp), "fn": int(fn),
                  "precision": tp / (tp + fp), "recall": tp / (tp + fn),
                  "f1": 2 * tp / (2 * tp + fp + fn)}
    return out


def main():
    metrics = load("llm_eval_metrics.json")
    table = pd.read_csv(REPORTS / "llm_vs_rules.csv")
    person = table[table["label_set"] == "person_labels"]

    closer = {"llm": 0, "rules": 0, "tie": 0}
    for _, r in pd.read_csv(REPORTS / "llm_disagreements.csv").iterrows():
        truth = codes(r["ai_labels"])
        a, b = len(codes(r["llm"]) ^ truth), len(codes(r["rules"]) ^ truth)
        closer["llm" if a < b else "rules" if b < a else "tie"] += 1

    ranks = pd.read_csv(REPORTS / "pain_point_ranking_compare.csv")
    spearman = {r: float(g["rank_in_retailer_rules"].corr(g["rank_in_retailer_llm"], method="spearman"))
                for r, g in ranks.groupby("retailer")}

    f1_diff = {}
    for key in ("ai_labels", "person_labels"):
        s = metrics[key]
        f1_diff[key] = {m + "_minus_rules": s[m]["micro"]["f1"] - s["rules"]["micro"]["f1"]
                        for m in ("llm", "hybrid")}

    labels = load("label_recheck_agreement.json")["per_stage_treating_person_as_truth"]
    out = {
        "api_spend": api_spend(metrics["prompt"]),
        "f1_difference": f1_diff,
        "disagreements_closer_to_ai_labels": closer,
        "person_labels_without_RS": micro_without(person, "Refunds & customer service"),
        "person_RS_labels_in_30": labels["RS"]["tp"] + labels["RS"]["fn"],
        "pain_point_rank_spearman": spearman,
    }
    (REPORTS / "llm_summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
