"""Step 40: Export tidy CSV files for the online dashboard.

Every file comes from results the earlier steps already produced.
No new analysis happens here, only reshaping.

Output: reports/dashboard_data/*.csv
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REP = ROOT / "reports"
OUT = REP / "dashboard_data"


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # Module 1
    rev = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    summ = rev.groupby("retailer").agg(reviews=("rating", "size"), avg_rating=("rating", "mean"),
                                       negative=("rating_group", lambda s: (s == "negative").sum()))
    summ.loc["All three"] = [len(rev), rev["rating"].mean(), (rev["rating_group"] == "negative").sum()]
    summ["negative_share"] = summ["negative"] / summ["reviews"]
    summ.round(4).reset_index().to_csv(OUT / "reviews_summary.csv", index=False)

    pain = pd.read_csv(REP / "pain_point_ranking.csv")
    pain.to_csv(OUT / "pain_points.csv", index=False)

    val = pd.read_csv(REP / "tag_validation.csv")
    val[val["sample"] == "test"].drop(columns="sample").to_csv(OUT / "tag_validation_test.csv", index=False)

    # Module 2
    f = pd.read_csv(REP / "m2_funnel_overall.csv")
    labels = {"view_item": "View item", "add_to_cart": "Add to cart", "begin_checkout": "Begin checkout",
              "add_payment_info": "Add payment info", "purchase": "Purchase"}
    f.insert(1, "step_label", f["step"].map(labels))
    f.insert(0, "step_order", range(1, len(f) + 1))
    f.to_csv(OUT / "funnel_steps.csv", index=False)

    seg = pd.read_csv(REP / "m2_funnel_segments.csv")
    seg["segment_type"] = seg["segment_type"].map({"device_category": "Device", "medium": "First-touch medium",
                                                   "user_type": "New vs returning"})
    seg.to_csv(OUT / "funnel_segments.csv", index=False)

    base = json.loads((REP / "m2_baselines.json").read_text())
    pd.DataFrame(list(base.items()), columns=["metric", "value"]).to_csv(OUT / "ga4_baselines.csv", index=False)

    # Module 3
    pd.read_csv(REP / "m3_kpis.csv").to_csv(OUT / "cj_kpis.csv", index=False)
    pd.read_csv(REP / "m3_rfm_segments.csv").to_csv(OUT / "rfm_segments.csv", index=False)
    did = pd.read_csv(REP / "m3_campaign_did.csv")
    did["label"] = ("Campaign " + did["campaign"].astype(str) + " · "
                    + did["outcome"].map({"total_spend": "total spend", "coupon_product_spend": "coupon-product spend"}))
    did.to_csv(OUT / "campaign_did.csv", index=False)
    pd.read_csv(REP / "m3_coupon_loyalty_groups.csv").to_csv(OUT / "coupon_groups.csv", index=False)

    # Module 4
    pw = pd.read_csv(REP / "m4_power_table.csv")
    pw.insert(0, "scenario", [f"+{m:g} pts" if i < 4 else "All users (diluted)"
                              for i, m in enumerate(pw["mde_abs_points"])])
    pw.to_csv(OUT / "ab_power.csv", index=False)
    des = json.loads((REP / "m4_design_numbers.json").read_text())
    pd.DataFrame(list(des.items()), columns=["metric", "value"]).to_csv(OUT / "ab_design.csv", index=False)

    for p in sorted(OUT.glob("*.csv")):
        print(p.name, len(pd.read_csv(p)), "rows")


if __name__ == "__main__":
    main()
