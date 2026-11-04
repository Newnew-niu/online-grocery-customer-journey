"""Step 7: Compare the keyword rules, the LLM and a "rules OR LLM" hybrid on the test sample.

Two sets of labels are used:
- ai_labels:     the original labels, made by an AI assistant in one pass (100 reviews)
- person_labels: blind labels from a person (30 of the same reviews)

CIs come from 10,000 bootstrap resamples of reviews. Differences are paired: every
method is scored on the same resample. A review the LLM failed on counts as "no stage".

Outputs:
- reports/llm_vs_rules.csv
- reports/llm_eval_metrics.json
- reports/llm_disagreements.csv (labels only)
- llm_upgrade/data/llm_disagreements_with_text.csv (git-ignored)
- reports/figures/m5_rules_vs_llm.png
"""
import json
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, labels_to_matrix, load_sample
from eval_metrics import bootstrap_ci, macro, micro, per_stage

sys.path.insert(0, str(ROOT / "src"))
import chart_style as cs  # noqa: E402
from journey_rules import STAGE_LABELS, tag_text  # noqa: E402

METHODS = ["rules", "llm", "hybrid"]
METHOD_NAMES = {"rules": "Keyword rules", "llm": "LLM", "hybrid": "Rules OR LLM"}
METRICS = ["precision", "recall", "f1"]


def frozen_prompt():
    return json.loads((REPORTS / "frozen_prompt.json").read_text(encoding="utf-8"))["frozen_prompt"]


def predictions(df):
    rules = np.array([[tag_text(t)[CODES[c]] for c in CODE_LIST] for t in df["full_text"]])
    llm = labels_to_matrix([x.split(";") for x in df["llm_labels"]])
    return {"rules": rules, "llm": llm, "hybrid": ((rules + llm) > 0).astype(int)}


def score(truth, preds, label_set):
    rows, summary = [], {"reviews": len(truth)}
    ci = bootstrap_ci(truth, preds)
    for name, pred in preds.items():
        stages = per_stage(truth, pred, CODE_LIST)
        for code, s in stages.items():
            rows.append({"label_set": label_set, "method": name, "level": STAGE_LABELS[CODES[code]],
                         **s, "support": s["tp"] + s["fn"]})
        mi, ma = micro(truth, pred), macro(truth, pred)
        tp = sum(s["tp"] for s in stages.values())
        fp = sum(s["fp"] for s in stages.values())
        fn = sum(s["fn"] for s in stages.values())
        rows.append({"label_set": label_set, "method": name, "level": "ALL STAGES (micro)",
                     "tp": tp, "fp": fp, "fn": fn, **mi, "support": tp + fn,
                     "precision_ci": ci[name]["precision"], "recall_ci": ci[name]["recall"],
                     "f1_ci": ci[name]["f1"]})
        rows.append({"label_set": label_set, "method": name, "level": "ALL STAGES (macro)", **ma})
        summary[name] = {"micro": mi, "macro": ma, "ci95": ci[name]}
    return rows, summary


def disagreements(df, preds):
    keep = []
    for i, r in df.iterrows():
        a, b = preds["rules"][i], preds["llm"][i]
        if (a != b).any():
            names = lambda row: ";".join(c for c, v in zip(CODE_LIST, row) if v)
            keep.append({"val_id": r["val_id"], "ai_labels": ";".join(r["labels"]),
                         "person_labels": r["person_labels"], "rules": names(a), "llm": names(b),
                         "full_text": r["full_text"]})
    out = pd.DataFrame(keep)
    out.drop(columns="full_text").to_csv(REPORTS / "llm_disagreements.csv", index=False)
    out.to_csv(DATA / "llm_disagreements_with_text.csv", index=False, encoding="utf-8-sig")
    return len(out)


def chart(result):
    cs.apply()
    sets = [("ai_labels", "AI-made labels (n=100)"), ("person_labels", "Person's blind labels (n=30)")]
    fig, axes = plt.subplots(2, 3, figsize=(9.5, 5.6), sharex=True, sharey=True)
    for r, (key, label) in enumerate(sets):
        for c, metric in enumerate(METRICS):
            ax = axes[r, c]
            for y, m in enumerate(METHODS):
                value = result[key][m]["micro"][metric]
                lo, hi = result[key][m]["ci95"][metric]
                ax.hlines(y, lo, hi, color=cs.SERIES[y], lw=2)
                ax.scatter(value, y, s=64, color=cs.SERIES[y], zorder=3,
                           edgecolor=cs.SURFACE, linewidth=2)
                ax.text(value, y + 0.2, f"{value:.2f}", ha="center", fontsize=8, color=cs.TEXT_2)
            ax.set_yticks(range(3), [METHOD_NAMES[m] for m in METHODS])
            ax.set_ylim(-0.5, 2.6)
            ax.set_xlim(0.4, 1.0)
            ax.grid(axis="y", visible=False)
            if r == 0:
                ax.set_title(metric.capitalize() if metric != "f1" else "F1")
        axes[r, 0].set_ylabel(label, fontsize=8)
    cs.title(fig, "Keyword rules vs LLM on the test sample (micro average, 95% bootstrap CI)")
    cs.source_note(fig, "Reviews: Google Play + App Store (Ireland). The 30 are a subset of the 100. "
                        "One LLM run with a prompt frozen on the dev sample.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(REPORTS / "figures" / "m5_rules_vs_llm.png", dpi=160)


def main():
    prompt = frozen_prompt()
    df = load_sample("test")
    tags = pd.read_csv(DATA / f"llm_tags_test_{prompt}.csv").fillna("")
    person = pd.read_csv(REPORTS / "test_recheck_labels.csv").fillna("")
    df = df.merge(tags, on=["val_id", "review_id"], validate="one_to_one")
    df = df.merge(person[["val_id", "person_labels"]], on="val_id", how="left")
    checked = df["person_labels"].notna()
    df["person_labels"] = df["person_labels"].fillna("")

    preds = predictions(df)
    rows, ai = score(labels_to_matrix(df["labels"]), preds, "ai_labels")
    sub = {k: v[checked.values] for k, v in preds.items()}
    truth_p = labels_to_matrix([x.split(";") for x in df.loc[checked, "person_labels"]])
    rows_p, human = score(truth_p, sub, "person_labels")

    run = json.loads((REPORTS / f"llm_run_test_{prompt}.json").read_text(encoding="utf-8"))
    result = {
        "prompt": prompt, "model": run["model"], "date": run["date"],
        "ai_labels": ai, "person_labels": human,
        "disagreements_rules_vs_llm": disagreements(df, preds),
        "llm_failures": run["failures"], "valid_quote_rate": run["valid_quote_rate"],
        "input_tokens": run["input_tokens"], "output_tokens": run["output_tokens"],
        "cost_usd": run["cost_usd"], "avg_latency_s": run["avg_latency_s"],
    }
    (REPORTS / "llm_eval_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    pd.DataFrame(rows + rows_p).to_csv(REPORTS / "llm_vs_rules.csv", index=False)
    chart(result)

    for key, label in (("ai_labels", "AI labels"), ("person_labels", "person's labels")):
        print(f"\n== {label}, n={result[key]['reviews']}")
        for m in METHODS:
            s = result[key][m]
            print(m, {k: round(v, 3) for k, v in s["micro"].items()},
                  "macro F1", round(s["macro"]["f1"], 3),
                  "F1 CI", [round(x, 3) for x in s["ci95"]["f1"]],
                  "F1 diff vs rules CI", s["ci95"].get("diff_vs_rules", {}).get("f1"))
    print({k: result[k] for k in ("disagreements_rules_vs_llm", "llm_failures", "valid_quote_rate",
                                  "cost_usd", "avg_latency_s")})


if __name__ == "__main__":
    main()
