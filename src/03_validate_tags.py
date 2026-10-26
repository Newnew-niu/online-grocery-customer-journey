"""Step 3: Check the keyword rules against hand labels.

We used two random samples of 100 negative reviews (rating 1-2):
- "dev" sample (seed 42): used to find rule mistakes and improve the rules.
- "test" sample (seed 2026, no overlap with dev): NOT used to write rules.
  The test scores are the honest ones to report.

Each review was read and labelled by hand without looking at the rule tags.
Labels: data/processed/{dev,test}_labels_manual.csv
Codes: AL account/login, SB search/browse, BA basket, SL delivery slot,
CP checkout/payment, SM substitutions/missing items, DC delivery/collection,
RS refunds/customer service, AP app performance, PL pricing/promotions/loyalty.

For each stage we report:
- precision: of the reviews the rules tagged, how many were right
- recall:    of the reviews that truly mention the stage, how many the rules found

Output: reports/tag_validation.csv
"""
import sys
from pathlib import Path

import pandas as pd

from journey_rules import STAGE_LABELS, tag_text

ROOT = Path(__file__).resolve().parents[1]
CODES = {
    "AL": "account_login", "SB": "search_browse", "BA": "basket_add_to_cart",
    "SL": "delivery_slot_booking", "CP": "checkout_payment",
    "SM": "substitutions_missing_items", "DC": "delivery_collection",
    "RS": "refunds_customer_service", "AP": "app_performance",
    "PL": "pricing_promotions_loyalty",
}


def score(name, show_errors=False):
    sample = pd.read_csv(ROOT / f"data/processed/{name}_sample_blind.csv")
    manual = pd.read_csv(ROOT / f"data/processed/{name}_labels_manual.csv").fillna("")
    df = sample.merge(manual, on="val_id")

    rule_tags = pd.DataFrame([tag_text(t) for t in df["full_text"]])
    rows = []
    for code, stage in CODES.items():
        truth = df["manual_labels"].str.split(";").map(lambda labels: code in labels).astype(int)
        pred = rule_tags[stage]
        tp = int(((pred == 1) & (truth == 1)).sum())
        fp = int(((pred == 1) & (truth == 0)).sum())
        fn = int(((pred == 0) & (truth == 1)).sum())
        rows.append({
            "sample": name,
            "stage": STAGE_LABELS[stage],
            "hand_labelled": int(truth.sum()),
            "rule_tagged": int(pred.sum()),
            "correct": tp,
            "precision": round(tp / (tp + fp), 2) if tp + fp else None,
            "recall": round(tp / (tp + fn), 2) if tp + fn else None,
        })
        if show_errors:
            for i in df.index[(pred == 1) & (truth == 0)]:
                print(f"FP {code} #{df.val_id[i]}: {df.full_text[i][:110]}")
            for i in df.index[(pred == 0) & (truth == 1)]:
                print(f"FN {code} #{df.val_id[i]}: {df.full_text[i][:110]}")

    res = pd.DataFrame(rows)
    tp = res["correct"].sum()
    fp = (res["rule_tagged"] - res["correct"]).sum()
    fn = (res["hand_labelled"] - res["correct"]).sum()
    res = pd.concat([res, pd.DataFrame([{
        "sample": name, "stage": "ALL STAGES (micro average)",
        "hand_labelled": res["hand_labelled"].sum(), "rule_tagged": res["rule_tagged"].sum(),
        "correct": tp, "precision": round(tp / (tp + fp), 2), "recall": round(tp / (tp + fn), 2),
    }])], ignore_index=True)
    return res


def main():
    show = "--errors" in sys.argv
    out = pd.concat([score("dev", show), score("test", show)], ignore_index=True)
    print(out.to_string(index=False))
    out.to_csv(ROOT / "reports/tag_validation.csv", index=False)


if __name__ == "__main__":
    main()
