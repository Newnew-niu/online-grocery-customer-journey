"""Step 12: SIMULATED daily SLA monitoring for the two tagging vendors, with a Lark Base export.

All 2,091 reviews were really tagged in one run on 2026-11-04. Here they are split into
simulated daily batches (seeded, so the split is the same every time), and each batch is
checked the way an ops team would check a vendor's daily delivery:
- metrics that need no gold labels: output volume, failure and retry rates, quote-check
  failures (LLM only), rules-vs-LLM disagreement, cost
- quality on a QA spot check: a random sample of the person-labelled reviews that fall in
  the batch, scored against the person's labels (sample size reported)
Each batch x vendor row is compared with the SIMULATED thresholds in
config/sla_thresholds_simulated.yaml and gets a breach flag and the reasons.

Real data: labels, quotes, tokens and retries per review. Simulated: the batches, their
dates, the thresholds and the owner roles. Columns that are simulated start with sim_.

Inputs (git-ignored ones are marked *):
  config/sla_thresholds_simulated.yaml, config/pricing.yaml, reports/test_recheck_labels_100.csv,
  data/llm_tags_all_journey_stage_v2.csv*, data/llm_cache/...*,
  ../data/processed/reviews_tagged.csv*, ../data/processed/test_sample_blind.csv*
Outputs:
  reports/lark_export/sim_daily_sla_by_batch_vendor.csv   one row per batch per vendor
  reports/lark_export/sim_sla_thresholds.csv              the thresholds, for a lookup table
No API calls.
"""
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, UPGRADE, labels_to_matrix
from eval_metrics import micro
from llm_client import MODEL, Cache, quote_is_exact

from journey_rules import tag_text  # noqa: E402  (original src/, put on the path by common)

CONFIG = UPGRADE / "config" / "sla_thresholds_simulated.yaml"
PRICING = UPGRADE / "config" / "pricing.yaml"
OUT_DIR = REPORTS / "lark_export"
PROMPT = "journey_stage_v2"
VENDORS = ["rules", "llm"]


def codes(cell):
    return [c for c in str(cell).split(";") if c and c != "nan"]


def assign_batches(review_ids, n_batches, seed, first_date):
    """Shuffle reviews with a seed and cut them into n near-equal simulated daily batches."""
    ids = np.asarray(list(review_ids))
    order = np.random.default_rng(seed).permutation(len(ids))
    start = date.fromisoformat(first_date)
    rows = []
    for b, part in enumerate(np.array_split(order, n_batches), start=1):
        for i in part:
            rows.append({"review_id": ids[i], "sim_batch_id": f"SIM-B{b:02d}",
                         "sim_batch_date": (start + timedelta(days=b - 1)).isoformat()})
    return pd.DataFrame(rows)


def qa_sample(batch, k, seed):
    """Random sample of up to k person-labelled reviews in the batch."""
    pool = batch[batch["person_labels"].notna()]
    if len(pool) <= k:
        return pool
    return pool.sample(k, random_state=seed)


def qa_scores(sample, vendor):
    if len(sample) == 0:
        return {"precision": None, "recall": None, "f1": None}
    truth = labels_to_matrix(list(sample["person_labels"]))
    pred = labels_to_matrix(list(sample[f"{vendor}_labels"]))
    return micro(truth, pred)


def check_breach(row, t):
    """Return (breach, reasons). Metrics that do not apply (None) are skipped."""
    rules = [
        ("output_volume", lambda v: v < t["min_output_volume"], f"volume below {t['min_output_volume']}"),
        ("failure_rate", lambda v: v > t["max_failure_rate"], f"failure rate above {t['max_failure_rate']}"),
        ("retry_rate", lambda v: v > t["max_retry_rate"], f"retry rate above {t['max_retry_rate']}"),
        ("quote_fail_rate", lambda v: v > t["max_quote_fail_rate"], f"quote failures above {t['max_quote_fail_rate']}"),
        ("disagreement_rate", lambda v: v > t["max_disagreement_rate"],
         f"rules-LLM disagreement above {t['max_disagreement_rate']}"),
        ("cost_per_1000_usd", lambda v: v > t["max_cost_per_1000_usd"],
         f"cost per 1,000 above ${t['max_cost_per_1000_usd']}"),
        ("qa_sample_size", lambda v: v < t["min_qa_sample"], f"QA sample below {t['min_qa_sample']}"),
        ("qa_f1", lambda v: v < t["min_qa_f1"], f"QA F1 below {t['min_qa_f1']}"),
    ]
    reasons = []
    for key, failed, text in rules:
        v = row.get(key)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        if failed(v):
            reasons.append(f"{text} ({v:.3g})" if isinstance(v, float) else f"{text} ({v})")
    return bool(reasons), "; ".join(reasons)


def batch_rows(reviews, cfg, prices):
    sim, t = cfg["simulation"], cfg["thresholds"]
    out = []
    for b_no, (bid, batch) in enumerate(reviews.groupby("sim_batch_id", sort=True), start=1):
        n = len(batch)
        differ = float((batch["rules_labels"].map(sorted) != batch["llm_labels"].map(sorted)).mean())
        sample = qa_sample(batch, sim["qa_sample_per_batch"], sim["seed"] + b_no)
        for v in VENDORS:
            labels = batch[f"{v}_labels"]
            if v == "llm":
                inp, outp = int(batch["input_tokens"].sum()), int(batch["output_tokens"].sum())
                cost = (inp * prices["input_per_million_usd"] + outp * prices["output_per_million_usd"]) / 1e6
                quotes = int(batch["quotes"].sum())
                extra = {"failure_rate": float((~batch["llm_ok"]).mean()),
                         "retry_rate": float((batch["attempts"] > 1).mean()),
                         "quotes_checked": quotes,
                         "quote_fail_rate": (quotes - int(batch["quotes_exact"].sum())) / quotes if quotes else 0.0,
                         "input_tokens": inp, "output_tokens": outp, "cost_usd": cost}
            else:
                extra = {"failure_rate": 0.0, "retry_rate": 0.0, "quotes_checked": None,
                         "quote_fail_rate": None, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            q = qa_scores(sample, v)
            row = {"sim_batch_id": bid, "sim_batch_date": batch["sim_batch_date"].iloc[0], "vendor": v,
                   "sim_owner_role": cfg["owners"][v], "output_volume": n,
                   "reviews_with_stage": int((labels.map(len) > 0).sum()),
                   "labels_produced": int(labels.map(len).sum()), **extra,
                   "cost_per_1000_usd": 1000 * extra["cost_usd"] / n, "disagreement_rate": differ,
                   "person_labelled_in_batch": int(batch["person_labels"].notna().sum()),
                   "qa_sample_size": len(sample), "qa_precision": q["precision"], "qa_recall": q["recall"],
                   "qa_f1": q["f1"]}
            breach, reasons = check_breach(row, t)
            row.update({"breach": "TRUE" if breach else "FALSE", "breach_reason": reasons,
                        "sim_status": "Open" if breach else "No action"})
            out.append(row)
    return pd.DataFrame(out)


def load_reviews(cfg):
    sim = cfg["simulation"]
    allrev = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")[["review_id", "full_text"]]
    tags = pd.read_csv(DATA / f"llm_tags_all_{PROMPT}.csv", keep_default_na=False)
    df = allrev.merge(tags[["review_id", "ok", "llm_labels", "evidence"]], on="review_id", validate="one_to_one")
    df["llm_ok"] = df["ok"].astype(str).str.lower() == "true"
    df["rules_labels"] = [[c for c in CODE_LIST if tag_text(x)[CODES[c]]] for x in df["full_text"]]
    df["llm_labels"] = df["llm_labels"].map(codes)
    ev = [json.loads(e) if e else {} for e in df["evidence"]]
    df["quotes"] = [len(e) for e in ev]
    df["quotes_exact"] = [sum(quote_is_exact(q, txt) for q in e.values()) for e, txt in zip(ev, df["full_text"])]
    cache = Cache()
    hits = [cache.get(MODEL, PROMPT, r) for r in df["review_id"]]
    if any(h is None for h in hits):
        raise SystemExit("Some reviews are missing from the LLM cache; cannot read tokens.")
    for k in ("attempts", "input_tokens", "output_tokens"):
        df[k] = [h[k] for h in hits]
    person = pd.read_csv(REPORTS / "test_recheck_labels_100.csv", dtype=str, keep_default_na=False)
    test = pd.read_csv(ROOT / "data/processed/test_sample_blind.csv")[["val_id", "review_id"]]
    person = person.assign(val_id=person["val_id"].astype(int)).merge(test, on="val_id", validate="one_to_one")
    df = df.merge(person[["review_id", "person_labels"]], on="review_id", how="left")
    df["person_labels"] = df["person_labels"].map(lambda x: codes(x) if isinstance(x, str) else None)
    batches = assign_batches(df["review_id"], sim["batches"], sim["seed"], sim["first_batch_date"])
    return df.merge(batches, on="review_id", validate="one_to_one")


def thresholds_table(t):
    meaning = {
        "min_output_volume": ("both", "reviews tagged per batch"),
        "max_failure_rate": ("both", "share of reviews with no answer after all retries"),
        "max_retry_rate": ("both", "share of reviews needing more than one attempt; cause not logged"),
        "max_quote_fail_rate": ("llm", "share of evidence quotes that are not exact substrings"),
        "max_disagreement_rate": ("both", "share of reviews where rules and LLM give a different label set"),
        "max_cost_per_1000_usd": ("both", "API cost per 1,000 reviews; prices VERIFY"),
        "min_qa_sample": ("both", "QA items checked per batch"),
        "min_qa_f1": ("both", "micro F1 on the QA sample vs the person's labels"),
    }
    return pd.DataFrame([{"sim_threshold": k, "value": v, "applies_to": meaning[k][0], "meaning": meaning[k][1]}
                         for k, v in t.items()], dtype=object)  # object keeps 250 as 250, not 250.0


def main():
    import yaml  # imported here so the tests need no PyYAML

    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    prices = yaml.safe_load(PRICING.read_text(encoding="utf-8"))["models"][MODEL]
    reviews = load_reviews(cfg)
    rows = batch_rows(reviews, cfg, prices)
    float_cols = rows.select_dtypes("float").columns
    rows[float_cols] = rows[float_cols].round(4)
    rows["quotes_checked"] = rows["quotes_checked"].astype("Int64")  # whole number; blank for rules
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUT_DIR / "sim_daily_sla_by_batch_vendor.csv", index=False, encoding="utf-8")
    thresholds_table(cfg["thresholds"]).to_csv(OUT_DIR / "sim_sla_thresholds.csv", index=False, encoding="utf-8")
    show = ["sim_batch_id", "vendor", "output_volume", "disagreement_rate", "retry_rate", "quote_fail_rate",
            "cost_per_1000_usd", "qa_sample_size", "qa_f1", "breach", "breach_reason"]
    with pd.option_context("display.width", 220, "display.max_colwidth", 70):
        print(rows[show].to_string(index=False))
    print(f"\nBreaches: {rows.groupby('vendor')['breach'].apply(lambda s: (s == 'TRUE').sum()).to_dict()}"
          f" | prices verified: {bool(prices.get('verified'))}")


if __name__ == "__main__":
    main()
