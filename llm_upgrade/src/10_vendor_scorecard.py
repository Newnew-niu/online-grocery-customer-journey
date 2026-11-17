"""Step 10: Vendor scorecard. Treat each tagger as an annotation vendor and score it.

Vendors:
- rules: the keyword rules from Module 1 (src/journey_rules.py)
- llm:   claude-haiku-5-5 with the frozen prompt journey_stage_v2

Quality and consistency use only the person's blind labels on the 100 test reviews
(reports/test_recheck_labels_100.csv). AI-made labels are not used here.
Efficiency, cost and reliability come from the logged run stats. The rules are timed
locally. No API calls are made.

Dimension scores (0-100):
- quality      = 100 x micro F1 against the person's labels
- consistency  = 100 x Cohen's kappa against the person's labels (floored at 0)
- efficiency   = 100 x reviews per minute / fastest vendor's reviews per minute
- cost         = 100 x cheapest cost / this vendor's cost (100 for the cheapest; 0 if the cheapest is free)
- reliability  = 100 x product of (1 - rate) over the rates that apply to the vendor
Overall = weighted mean of the five, with weights from config/scorecard_weights.yaml.

Inputs (git-ignored ones are marked *):
  reports/test_recheck_labels_100.csv, reports/llm_run_all_journey_stage_v2.json,
  reports/frozen_prompt.json, config/scorecard_weights.yaml,
  data/llm_tags_test_journey_stage_v2.csv*, data/llm_tags_all_journey_stage_v2.csv*,
  ../data/processed/test_sample_blind.csv*, ../data/processed/reviews_tagged.csv*
Outputs:
  reports/vendor_scorecard.csv            one row per vendor: raw metrics, scores, overall
  reports/vendor_scorecard_by_stage.csv   per-stage precision, recall, F1 per vendor
  reports/vendor_scorecard_sensitivity.csv
  reports/vendor_timing_rules.json        local timing of the rules (kept; use --retime to redo)
  reports/vendor_scorecard.md             summary and recommendation
  reports/figures/ops_vendor_scorecard.png
"""
import argparse
import json
import time
from datetime import date

import numpy as np
import pandas as pd

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, UPGRADE, labels_to_matrix
from eval_metrics import bootstrap_ci, cohen_kappa, macro, micro, per_stage

from journey_rules import STAGE_LABELS, tag_text  # noqa: E402

CONFIG = UPGRADE / "config" / "scorecard_weights.yaml"
DIMENSIONS = ["quality", "consistency", "efficiency", "cost", "reliability"]
VENDORS = ["rules", "llm"]
VENDOR_NAMES = {"rules": "Keyword rules", "llm": "LLM (Haiku, prompt v2)"}
N_BOOT = 10000
SEED = 2026


# ---------- small pure helpers (tested in tests/test_vendor_scorecard.py) ----------

def codes(cell):
    return [c for c in str(cell).split(";") if c and c != "nan"]


def rules_matrix(texts):
    return np.array([[tag_text(t)[CODES[c]] for c in CODE_LIST] for t in texts], dtype=int)


def relative_higher_better(values):
    best = max(values.values())
    return {k: 100 * v / best if best else 0.0 for k, v in values.items()}


def relative_lower_better(values):
    best = min(values.values())
    return {k: 100.0 if v == best else (100 * best / v if v else 0.0) for k, v in values.items()}


def reliability_score(rates):
    """rates: {name: rate or None}. None means not applicable and is skipped."""
    out = 1.0
    for r in rates.values():
        if r is not None:
            out *= 1 - r
    return 100 * out


def dimension_scores(raw):
    """raw: {vendor: {micro_f1, kappa_vs_person, reviews_per_minute, cost_per_1000_usd, rates}}"""
    eff = relative_higher_better({v: r["reviews_per_minute"] for v, r in raw.items()})
    cost = relative_lower_better({v: r["cost_per_1000_usd"] for v, r in raw.items()})
    return {v: {"quality": 100 * r["micro_f1"],
                "consistency": 100 * max(0.0, r["kappa_vs_person"]),
                "efficiency": eff[v], "cost": cost[v],
                "reliability": reliability_score(r["rates"])}
            for v, r in raw.items()}


def overall(scores, weights):
    total = sum(weights[d] for d in DIMENSIONS)
    return sum(scores[d] * weights[d] for d in DIMENSIONS) / total


def sensitivity(scores, weights, draws, seed):
    """Overall score per vendor under other weight sets."""
    cases = [("agreed weights", weights),
             ("equal weights", {d: 1 for d in DIMENSIONS}),
             ("quality only", {d: int(d == "quality") for d in DIMENSIONS}),
             ("quality + consistency only", {d: int(d in ("quality", "consistency")) for d in DIMENSIONS})]
    cases += [(f"without {d}", {**weights, d: 0}) for d in DIMENSIONS]
    rows = []
    for name, w in cases:
        s = {v: overall(scores[v], w) for v in scores}
        rows.append({"scenario": name, **{f"w_{d}": w[d] for d in DIMENSIONS},
                     **{f"overall_{v}": s[v] for v in scores},
                     "winner": winner(s)})
    rng = np.random.default_rng(seed)
    wins = {v: 0 for v in scores} | {"tie": 0}
    for w in rng.dirichlet(np.ones(len(DIMENSIONS)), draws):
        wd = dict(zip(DIMENSIONS, w))
        wins[winner({v: overall(scores[v], wd) for v in scores})] += 1
    rows.append({"scenario": f"random weights ({draws:,} draws)",
                 **{f"overall_{v}": None for v in scores},
                 "winner": "; ".join(f"{k} {n / draws:.1%}" for k, n in wins.items())})
    return pd.DataFrame(rows), {k: n / draws for k, n in wins.items()}


def md_table(df):
    """A plain markdown table, so no extra package is needed."""
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]
    return "\n".join(lines)


def recommendation(totals, diffs, llm_cost_per_1000, llm_change_rate, random_share):
    """Return (vendor, paragraph) from the numbers. diffs: one row per label round
    with f1_rules, f1_llm, ci_low, ci_high, ci_excludes_zero (round 'all100' is the main one)."""
    d = diffs.set_index("label_round")
    a = d.loc["all100"]
    weighted = winner(totals)
    quality = "llm" if a["f1_llm"] > a["f1_rules"] else "rules"
    other = {"rules": "llm", "llm": "rules"}
    name = {"rules": "the keyword rules", "llm": "the LLM tagger"}
    f1 = (f"On the person's labels for {int(a['reviews'])} reviews, micro F1 is {a['f1_rules']:.2f} for the rules "
          f"and {a['f1_llm']:.2f} for the LLM (difference {a['f1_llm'] - a['f1_rules']:+.2f}, "
          f"95% CI {a['ci_low']:+.2f} to {a['ci_high']:+.2f}).")
    scores = (f"With the agreed weights the rules score {totals['rules']:.1f} and the LLM {totals['llm']:.1f}.")
    if weighted == quality or not a["ci_excludes_zero"]:
        noise = (" The quality gap is within noise, because the CI includes zero."
                 if not a["ci_excludes_zero"] else "")
        text = (f"**Recommendation: use {name[weighted]} as the main vendor.** {scores} {f1}{noise} "
                f"The LLM costs ${llm_cost_per_1000:.2f} per 1,000 reviews and changed its labels on "
                f"{llm_change_rate:.0%} of dev reviews when run again; the rules are free and give the same "
                f"labels every time. Keep {name[other[weighted]]} as a second opinion on reviews where the two disagree.")
        return weighted, text
    split = ""
    if {"first30", "rest70"} <= set(d.index):
        f30, r70 = d.loc["first30"], d.loc["rest70"]
        same_sign = (f30["f1_llm"] - f30["f1_rules"]) * (r70["f1_llm"] - r70["f1_rules"]) > 0
        if not same_sign:
            split = (f" But the gap is not stable across the two labelling rounds. On the 30 reviews labelled before "
                     f"the LLM test run, the rules were ahead ({f30['f1_rules']:.2f} vs {f30['f1_llm']:.2f}). On the 70 "
                     f"labelled after its results were published, the LLM was ahead ({r70['f1_llm']:.2f} vs "
                     f"{r70['f1_rules']:.2f}). So the quality lead is real on this data but not yet settled.")
    text = (f"**Recommendation: use {name[quality]} as the main vendor, with {name[other[quality]]} as a "
            f"cross-check.** {scores} That lead comes from cost and speed, which are scored relative to the best "
            f"vendor: a free, local vendor gets full marks and any paid vendor almost none, even though the LLM "
            f"costs only ${llm_cost_per_1000:.2f} per 1,000 reviews. With random weights the rules still lead in "
            f"{random_share['rules']:.0%} of draws for the same reason. Quality is the main job of an annotation "
            f"vendor, and there the LLM is better. {f1}{split} The LLM also changed its labels on "
            f"{llm_change_rate:.0%} of dev reviews when run again, so a repeat check and QA sampling are needed. "
            f"Next step: label a fresh blind sample before looking at any tagger output, and rescore.")
    return quality, text


def winner(s):
    a, b = s["rules"], s["llm"]
    return "tie" if abs(a - b) < 1e-9 else ("rules" if a > b else "llm")


def kappa_bootstrap(truth, preds, n_boot=N_BOOT, seed=SEED):
    """95% CIs for kappa per vendor and for llm minus rules, on the same resamples."""
    rng = np.random.default_rng(seed)
    draws = {v: [] for v in preds}
    for _ in range(n_boot):
        i = rng.integers(0, len(truth), len(truth))
        for v, p in preds.items():
            draws[v].append(cohen_kappa(truth[i], p[i]))
    ci = lambda x: [float(q) for q in np.nanpercentile(np.array(x, dtype=float), [2.5, 97.5])]
    out = {v: ci(d) for v, d in draws.items()}
    out["llm_minus_rules"] = ci(np.array(draws["llm"], dtype=float) - np.array(draws["rules"], dtype=float))
    return out


# ---------- measurements ----------

def time_rules(texts, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        rules_matrix(texts)
        best = min(best, time.perf_counter() - t0)
    return {"reviews": len(texts), "repeats": repeats, "best_seconds": best,
            "reviews_per_minute": 60 * len(texts) / best, "measured_on": str(date.today()),
            "note": "Best of the repeats, one process on the owner's laptop. Time to tag only; "
                    "reading files is not included."}


def load_inputs():
    import yaml  # imported here so the tests need no PyYAML

    load = lambda p: json.loads(p.read_text(encoding="utf-8"))
    person = pd.read_csv(REPORTS / "test_recheck_labels_100.csv", dtype=str, keep_default_na=False)
    person["val_id"] = person["val_id"].astype(int)
    test = pd.read_csv(ROOT / "data/processed/test_sample_blind.csv")
    tags = pd.read_csv(DATA / "llm_tags_test_journey_stage_v2.csv", keep_default_na=False)
    df = person.merge(test[["val_id", "review_id", "full_text"]], on="val_id", validate="one_to_one")
    df = df.merge(tags[["val_id", "llm_labels"]], on="val_id", validate="one_to_one")
    allrev = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")[["review_id", "full_text"]]
    alltags = pd.read_csv(DATA / "llm_tags_all_journey_stage_v2.csv", keep_default_na=False)
    allrev = allrev.merge(alltags[["review_id", "llm_labels"]], on="review_id", validate="one_to_one")
    return {"test": df, "all": allrev,
            "run": load(REPORTS / "llm_run_all_journey_stage_v2.json"),
            "frozen": load(REPORTS / "frozen_prompt.json"),
            "config": yaml.safe_load(CONFIG.read_text(encoding="utf-8"))}


def chart(scores, overall_by_vendor, weights):
    import matplotlib.pyplot as plt  # imported here so the tests need no matplotlib
    import chart_style as cs  # original src/, put on the path by common

    cs.apply()
    rows = DIMENSIONS[::-1] + ["overall"]
    labels = {d: f"{d.capitalize()} ({weights[d]})" for d in DIMENSIONS} | {"overall": "Weighted overall"}
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    h = 0.36
    for k, v in enumerate(VENDORS):
        vals = [scores[v][d] for d in DIMENSIONS[::-1]] + [overall_by_vendor[v]]
        y = np.arange(len(rows)) + (0.5 - k) * (h + 0.04)  # rules on top, as in the legend
        ax.barh(y, vals, height=h, color=cs.SERIES[k], label=VENDOR_NAMES[v])
        for yy, val in zip(y, vals):
            ax.text(val + 1, yy, f"{val:.0f}", va="center", fontsize=8, color=cs.TEXT_2)
    ax.set_yticks(range(len(rows)), [labels[r] for r in rows])
    ax.axhline(len(rows) - 1.5, color=cs.GRID, lw=1)
    ax.set_xlim(0, 112)
    ax.set_xlabel("Score (0-100), weight in brackets")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=8)
    cs.title(fig, "Vendor scorecard: keyword rules vs LLM tagger")
    cs.source_note(fig, "Quality and consistency: person's blind labels on 100 test reviews. "
                        "Efficiency, cost, reliability: logged run stats. See reports/vendor_scorecard.csv.")
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(REPORTS / "figures" / "ops_vendor_scorecard.png", dpi=160)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retime", action="store_true", help="time the rules again")
    args = ap.parse_args()

    x = load_inputs()
    cfg, run, df = x["config"], x["run"], x["test"]
    weights = cfg["weights"]

    # Quality and consistency on the person's labels.
    truth = labels_to_matrix(df["person_labels"].map(codes))
    preds = {"rules": rules_matrix(df["full_text"]), "llm": labels_to_matrix(df["llm_labels"].map(codes))}
    f1_ci = bootstrap_ci(truth, preds, n_boot=N_BOOT, seed=SEED)
    k_ci = kappa_bootstrap(truth, preds)
    rounds = {r: (df["label_round"] == r).values for r in ("first30", "rest70")}

    # Rules across all 2,091 reviews: timing, repeat check, agreement with the LLM.
    all_rules = rules_matrix(x["all"]["full_text"])
    all_rules_again = rules_matrix(x["all"]["full_text"])
    all_llm = labels_to_matrix(x["all"]["llm_labels"].map(codes))
    timing_path = REPORTS / "vendor_timing_rules.json"
    if args.retime or not timing_path.exists():
        timing_path.write_text(json.dumps(time_rules(x["all"]["full_text"]), indent=2), encoding="utf-8")
    timing = json.loads(timing_path.read_text(encoding="utf-8"))

    n = run["reviews"]
    raw = {
        "rules": {"rates": {"failure_rate": 0.0, "retry_rate": 0.0, "inexact_quote_rate": None,
                            "repeat_run_change_rate": float((all_rules != all_rules_again).any(axis=1).mean())},
                  "reviews_per_minute": timing["reviews_per_minute"], "cost_per_1000_usd": 0.0},
        "llm": {"rates": {"failure_rate": run["failures"] / n, "retry_rate": run["retries"] / n,
                          "inexact_quote_rate": 1 - run["valid_quote_rate"],
                          "repeat_run_change_rate": 1 - x["frozen"]["same_labels_on_rerun"]["journey_stage_v2"]},
                "reviews_per_minute": 60 / run["avg_latency_s"],
                "cost_per_1000_usd": 1000 * run["cost_usd"] / n},
    }
    for v in VENDORS:
        mi, ma = micro(truth, preds[v]), macro(truth, preds[v])
        raw[v].update({"precision": mi["precision"], "recall": mi["recall"], "micro_f1": mi["f1"],
                       "macro_f1": ma["f1"], "f1_ci95": f1_ci[v]["f1"],
                       "kappa_vs_person": cohen_kappa(truth, preds[v]), "kappa_ci95": k_ci[v],
                       **{f"micro_f1_{r}": micro(truth[m], preds[v][m])["f1"] for r, m in rounds.items()}})
    scores = dimension_scores(raw)
    totals = {v: overall(scores[v], weights) for v in VENDORS}
    sens, random_share = sensitivity(scores, weights, cfg["sensitivity"]["random_draws"],
                                     cfg["sensitivity"]["seed"])

    between = {"kappa_rules_vs_llm_test100": cohen_kappa(preds["rules"], preds["llm"]),
               "kappa_rules_vs_llm_all": cohen_kappa(all_rules, all_llm),
               "reviews_all": len(all_llm),
               "share_reviews_rules_llm_differ_all": float((all_rules != all_llm).any(axis=1).mean())}
    diff_rows = []
    for name, mask in (("all100", np.ones(len(truth), dtype=bool)), *rounds.items()):
        t, p = truth[mask], {v: preds[v][mask] for v in VENDORS}
        ci = bootstrap_ci(t, p, n_boot=N_BOOT, seed=SEED)["llm"]["diff_vs_rules"]["f1"]
        fr, fl = micro(t, p["rules"])["f1"], micro(t, p["llm"])["f1"]
        diff_rows.append({"label_round": name, "reviews": int(mask.sum()), "f1_rules": fr, "f1_llm": fl,
                          "f1_llm_minus_rules": fl - fr, "ci_low": ci[0], "ci_high": ci[1],
                          "ci_excludes_zero": bool(ci[0] > 0 or ci[1] < 0)})
    diffs = pd.DataFrame(diff_rows)
    diff_f1 = f1_ci["llm"]["diff_vs_rules"]["f1"]

    # ---- write tables ----
    rows = []
    for v in VENDORS:
        r = raw[v]
        rows.append({
            "vendor": v, "vendor_name": VENDOR_NAMES[v], "eval_reviews": len(truth),
            "precision": r["precision"], "recall": r["recall"], "micro_f1": r["micro_f1"],
            "micro_f1_ci_low": r["f1_ci95"][0], "micro_f1_ci_high": r["f1_ci95"][1],
            "macro_f1": r["macro_f1"], "micro_f1_first30": r["micro_f1_first30"],
            "micro_f1_rest70": r["micro_f1_rest70"],
            "kappa_vs_person": r["kappa_vs_person"], "kappa_ci_low": r["kappa_ci95"][0],
            "kappa_ci_high": r["kappa_ci95"][1],
            "reviews_per_minute": r["reviews_per_minute"],
            "efficiency_basis": ("local timing, one process (vendor_timing_rules.json)" if v == "rules"
                                 else "60 / mean logged latency, one worker (llm_run_all_journey_stage_v2.json)"),
            "cost_per_1000_usd": r["cost_per_1000_usd"],
            **{k: ("n/a" if val is None else val) for k, val in r["rates"].items()},
            **{f"score_{d}": scores[v][d] for d in DIMENSIONS},
            "overall_score": totals[v],
        })
    pd.DataFrame(rows).to_csv(REPORTS / "vendor_scorecard.csv", index=False)

    stage_rows = []
    for v in VENDORS:
        for c, s in per_stage(truth, preds[v], CODE_LIST).items():
            stage_rows.append({"vendor": v, "stage_code": c, "stage": STAGE_LABELS[CODES[c]],
                               "person_labelled": s["tp"] + s["fn"], **s})
    pd.DataFrame(stage_rows).to_csv(REPORTS / "vendor_scorecard_by_stage.csv", index=False)
    sens.to_csv(REPORTS / "vendor_scorecard_sensitivity.csv", index=False)
    diffs.to_csv(REPORTS / "vendor_scorecard_f1_diff.csv", index=False)
    chart(scores, totals, weights)
    write_summary(raw, scores, totals, weights, sens, random_share, between, diffs, k_ci, timing, len(truth), run)
    print(pd.DataFrame(rows).set_index("vendor")[["micro_f1", "kappa_vs_person", "reviews_per_minute",
                                                   "cost_per_1000_usd", "overall_score"]].round(3).to_string())
    print("F1 diff llm-rules CI", [round(q, 3) for q in diff_f1], "| random weights:", random_share)


def write_summary(raw, scores, totals, weights, sens, random_share, between, diffs, k_ci, timing, n, run):
    r, l = raw["rules"], raw["llm"]
    f = lambda x: f"{x:.2f}"
    _, rec = recommendation(totals, diffs, l["cost_per_1000_usd"], l["rates"]["repeat_run_change_rate"],
                            random_share)
    diff_t = pd.DataFrame({
        "Labels": diffs["label_round"].map({"all100": "all 100", "first30": "first 30 (before test run)",
                                            "rest70": "other 70 (after results)"}),
        "Reviews": diffs["reviews"],
        "F1 rules": diffs["f1_rules"].map(f), "F1 LLM": diffs["f1_llm"].map(f),
        "LLM - rules (95% CI)": [f"{a:+.2f} ({b:+.2f} to {c:+.2f})" for a, b, c in
                                 zip(diffs["f1_llm_minus_rules"], diffs["ci_low"], diffs["ci_high"])],
    })
    table = pd.DataFrame({
        "Dimension (weight)": [f"{d.capitalize()} ({weights[d]})" for d in DIMENSIONS] + ["**Overall**"],
        VENDOR_NAMES["rules"]: [f"{scores['rules'][d]:.1f}" for d in DIMENSIONS] + [f"**{totals['rules']:.1f}**"],
        VENDOR_NAMES["llm"]: [f"{scores['llm'][d]:.1f}" for d in DIMENSIONS] + [f"**{totals['llm']:.1f}**"],
    })
    sens_t = sens[["scenario", "overall_rules", "overall_llm", "winner"]].copy()
    for c in ("overall_rules", "overall_llm"):
        sens_t[c] = sens_t[c].map(lambda x: "" if pd.isna(x) else f"{x:.1f}")
    pct = lambda x: f"{x:.1%}"
    text = f"""# Vendor scorecard

Made by `src/10_vendor_scorecard.py`. Weights from `config/scorecard_weights.yaml`. All numbers below are in
`reports/vendor_scorecard.csv`, `reports/vendor_scorecard_by_stage.csv` and `reports/vendor_scorecard_sensitivity.csv`
unless another file is named.
Prices behind the LLM cost are from `src/llm_client.py` and are not yet checked: **VERIFY**.

Each tagger is treated as an annotation vendor. Quality is measured only against the person's blind labels on the
{n} test reviews (`reports/test_recheck_labels_100.csv`). The first 30 were labelled before the LLM test run and the
other 70 after its results were published.

![Vendor scorecard](figures/ops_vendor_scorecard.png)

## Recommendation

{rec}

## Quality gap by labelling round

Source: `reports/vendor_scorecard_f1_diff.csv` (10,000 paired bootstrap resamples of reviews).

{md_table(diff_t)}

## Scores

{md_table(table)}

## Raw metrics

| Metric | Keyword rules | LLM | Source |
|---|---|---|---|
| Micro precision / recall | {f(r['precision'])} / {f(r['recall'])} | {f(l['precision'])} / {f(l['recall'])} | person's labels, n={n} |
| Micro F1 (95% CI) | {f(r['micro_f1'])} ({f(r['f1_ci95'][0])}-{f(r['f1_ci95'][1])}) | {f(l['micro_f1'])} ({f(l['f1_ci95'][0])}-{f(l['f1_ci95'][1])}) | 10,000 paired bootstrap resamples |
| Micro F1, first 30 / other 70 | {f(r['micro_f1_first30'])} / {f(r['micro_f1_rest70'])} | {f(l['micro_f1_first30'])} / {f(l['micro_f1_rest70'])} | labelling rounds |
| Macro F1 | {f(r['macro_f1'])} | {f(l['macro_f1'])} | stages with no cases are skipped |
| Kappa vs person (95% CI) | {f(r['kappa_vs_person'])} ({f(r['kappa_ci95'][0])}-{f(r['kappa_ci95'][1])}) | {f(l['kappa_vs_person'])} ({f(l['kappa_ci95'][0])}-{f(l['kappa_ci95'][1])}) | over {n} x 10 review-stage cells |
| Reviews per minute | {r['reviews_per_minute']:,.0f} | {l['reviews_per_minute']:.1f} | rules: `reports/vendor_timing_rules.json`; LLM: 60 / mean latency in `reports/llm_run_all_journey_stage_v2.json` |
| Cost per 1,000 reviews (USD) | {r['cost_per_1000_usd']:.2f} | {l['cost_per_1000_usd']:.4f} | LLM: `cost_usd` / `reviews` in `reports/llm_run_all_journey_stage_v2.json`. Prices: VERIFY |
| Failure rate | {pct(r['rates']['failure_rate'])} | {pct(l['rates']['failure_rate'])} | `reports/llm_run_all_journey_stage_v2.json` |
| Retry rate | {pct(r['rates']['retry_rate'])} | {pct(l['rates']['retry_rate'])} | same; retry reasons were not logged |
| Inexact-quote rate | n/a (no quotes) | {pct(l['rates']['inexact_quote_rate'])} | same |
| Repeat-run change rate | {pct(r['rates']['repeat_run_change_rate'])} | {pct(l['rates']['repeat_run_change_rate'])} | rules: rerun on all 2,091 here; LLM: `reports/frozen_prompt.json` (100 dev reviews) |

- Kappa difference, LLM minus rules: {k_ci['llm_minus_rules'][0]:+.2f} to {k_ci['llm_minus_rules'][1]:+.2f} (95% CI).
- Agreement between the two vendors: kappa {f(between['kappa_rules_vs_llm_test100'])} on the {n} test reviews and
  {f(between['kappa_rules_vs_llm_all'])} on all {between['reviews_all']:,} reviews. They give a different label set on
  {between['share_reviews_rules_llm_differ_all']:.0%} of all reviews. Part of this is by design: the rules tag any
  mention, the LLM tags problems only, and most of the 2,091 reviews are positive.
- Refusals are not counted separately. A refusal would be retried, and there were {run['retries']} retries
  with no logged reason. NOT AVAILABLE.

## Weight sensitivity

{md_table(sens_t)}

## How to read this

- Efficiency and cost are relative to the best vendor. With two vendors and one of them free and local, these two
  dimensions give the rules full marks and the LLM almost none. The sensitivity table shows what happens without them.
- LLM speed is per worker. The run used 8 parallel workers, but the wall-clock time was not logged, so real throughput
  is NOT AVAILABLE.
- The rules timing was measured on {timing['measured_on']} on one laptop. It is kept in `reports/vendor_timing_rules.json` so
  reruns give the same scores. Run with `--retime` to measure again.
- Per-stage results are in `reports/vendor_scorecard_by_stage.csv`. Rare stages have 1-3 person labels, so per-stage scores are not reliable alone.
- The LLM prompt follows the "problems only" rule used for the labels. The rules count any mention. This favours the LLM a little.
"""
    (REPORTS / "vendor_scorecard.md").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
