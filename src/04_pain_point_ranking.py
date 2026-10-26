"""Step 4: Rank pain points by journey stage, per retailer.

Main measure: share of NEGATIVE reviews (1-2 stars) that mention each stage.
One review can mention more than one stage, so shares add up to more than 100%.
We also give a 95% confidence interval (Wilson method), because some
retailers have few reviews (SuperValu: 143 negative reviews).

Second measure: average star rating of ALL reviews that mention the stage.

Check: we compare rule-based shares with hand-label shares on the 200
hand-labelled negative reviews, to see if the ranking is the same.

Outputs:
- reports/pain_point_ranking.csv
- reports/figures/m1_pain_points_by_retailer.png
- reports/figures/m1_avg_rating_by_stage.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.stats.proportion import proportion_confint

import chart_style as cs
from journey_rules import STAGE_LABELS, STAGES, tag_text

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
RETAILERS = ["Tesco", "Dunnes Stores", "SuperValu"]
IN_STORE = r"\b(in[- ]store|in the store|till|tills|self[- ]?(scan|serve|service)|at the checkout|at checkout|in the shop|queue)\b"


def main():
    df = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    stages = list(STAGES)
    neg = df[df["rating_group"] == "negative"]

    # ---- ranking table ----
    rows = []
    for r in RETAILERS + ["All three"]:
        sub = neg if r == "All three" else neg[neg["retailer"] == r]
        allr = df if r == "All three" else df[df["retailer"] == r]
        n = len(sub)
        for s in stages:
            k = int(sub[s].sum())
            lo, hi = proportion_confint(k, n, method="wilson")
            rows.append({
                "retailer": r, "stage": STAGE_LABELS[s], "negative_reviews": n,
                "negative_mentioning": k, "share_of_negative": round(k / n, 3),
                "ci_low": round(lo, 3), "ci_high": round(hi, 3),
                "avg_rating_when_mentioned": round(allr.loc[allr[s] == 1, "rating"].mean(), 2),
                "reviews_mentioning_any_rating": int(allr[s].sum()),
            })
    rank = pd.DataFrame(rows)
    rank["rank_in_retailer"] = rank.groupby("retailer")["share_of_negative"].rank(ascending=False, method="min").astype(int)
    rank = rank.sort_values(["retailer", "rank_in_retailer"])
    rank.to_csv(ROOT / "reports/pain_point_ranking.csv", index=False)

    for r in RETAILERS + ["All three"]:
        t = rank[rank.retailer == r]
        print(f"\n== {r} (negative reviews: {t.negative_reviews.iloc[0]})")
        print(t[["rank_in_retailer", "stage", "negative_mentioning", "share_of_negative",
                 "ci_low", "ci_high", "avg_rating_when_mentioned"]].to_string(index=False))

    # ---- extra context ----
    untagged = neg[neg["n_stages"] == 0]
    print(f"\nNegative reviews with no stage tag: {len(untagged)} of {len(neg)} ({len(untagged)/len(neg):.1%})")
    print("Median words in untagged negative reviews:", untagged["n_words"].median())
    in_store = neg["full_text"].str.lower().str.contains(IN_STORE, regex=True)
    print(f"Negative reviews that mention using the app IN STORE: {in_store.sum()} ({in_store.mean():.1%})")
    print(neg.assign(in_store=in_store).groupby("retailer")["in_store"].mean().round(3))
    print("\nAverage rating per retailer:", df.groupby("retailer")["rating"].mean().round(2).to_dict())
    print("Share negative per retailer:", (df.assign(neg=df.rating <= 2).groupby("retailer")["neg"].mean().round(3)).to_dict())

    # ---- check ranking against hand labels (200 reviews) ----
    codes = {"AL": "account_login", "SB": "search_browse", "BA": "basket_add_to_cart",
             "SL": "delivery_slot_booking", "CP": "checkout_payment", "SM": "substitutions_missing_items",
             "DC": "delivery_collection", "RS": "refunds_customer_service", "AP": "app_performance",
             "PL": "pricing_promotions_loyalty"}
    hand = []
    for name in ["dev", "test"]:
        s = pd.read_csv(ROOT / f"data/processed/{name}_sample_blind.csv")
        m = pd.read_csv(ROOT / f"data/processed/{name}_labels_manual.csv").fillna("")
        hand.append(s.merge(m, on="val_id"))
    hand = pd.concat(hand, ignore_index=True)
    rules = pd.DataFrame([tag_text(t) for t in hand["full_text"]])
    check = pd.DataFrame({
        "stage": [STAGE_LABELS[v] for v in codes.values()],
        "hand_label_share": [hand["manual_labels"].str.split(";").map(lambda x, c=c: c in x).mean() for c in codes],
        "rule_share": [rules[v].mean() for v in codes.values()],
    }).sort_values("hand_label_share", ascending=False)
    print("\nRanking check on 200 hand-labelled negative reviews:\n", check.round(3).to_string(index=False))
    check.round(3).to_csv(ROOT / "reports/pain_point_hand_vs_rules.csv", index=False)

    # ---- chart 1: share of negative reviews by stage and retailer ----
    cs.apply()
    order = (rank[rank.retailer == "All three"].sort_values("share_of_negative")["stage"].tolist())
    fig, ax = plt.subplots(figsize=(9, 6.6))
    y = np.arange(len(order))
    h = 0.26
    for i, r in enumerate(RETAILERS):
        t = rank[rank.retailer == r].set_index("stage").loc[order]
        pos = y + (1 - i) * h
        ax.barh(pos, t["share_of_negative"] * 100, height=h - 0.03, color=cs.RETAILER_COLORS[r],
                label=f"{r} (n={t.negative_reviews.iloc[0]})")
        for p, v in zip(pos, t["share_of_negative"] * 100):
            ax.text(v + 0.6, p, f"{v:.0f}%", va="center", fontsize=7.5, color=cs.TEXT_2)
    ax.set_yticks(y, order)
    ax.set_xlabel("Share of negative (1-2 star) reviews that mention the stage (%)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(rank.share_of_negative) * 100 + 8)
    ax.legend(loc="lower right", title="Retailer (negative reviews)", title_fontsize=9)
    cs.title(fig, "Each retailer has a different top complaint:\n"
                  "SuperValu = app speed, Dunnes = vouchers/prices, Tesco = speed, loyalty and login")
    cs.source_note(fig, "Source: Google Play + App Store reviews (Ireland), Oct 2024 - Oct 2026. "
                        "A review can mention several stages. Reviews are self-selected.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.92))
    fig.savefig(FIG / "m1_pain_points_by_retailer.png", dpi=160)

    # ---- chart 2: average rating when a stage is mentioned ----
    t = rank[rank.retailer == "All three"].sort_values("avg_rating_when_mentioned", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 5.4))
    yy = np.arange(len(t))
    ax.hlines(yy, 1, t["avg_rating_when_mentioned"], color=cs.GRID, lw=2)
    ax.scatter(t["avg_rating_when_mentioned"], yy, s=70, color=cs.SERIES[0], zorder=3,
               edgecolor=cs.SURFACE, linewidth=2)
    ax.set_yticks(yy, t["stage"])
    for y0, (v, n) in zip(yy, zip(t["avg_rating_when_mentioned"], t["reviews_mentioning_any_rating"])):
        ax.text(v + 0.1, y0 + 0.28, f"{v:.2f} (n={n})", va="center", fontsize=8, color=cs.TEXT_2)
    overall = df["rating"].mean()
    ax.axvline(overall, color=cs.TEXT_2, lw=1, ls="--")
    ax.text(overall + 0.04, 0.5, f"average of all\nreviews: {overall:.2f}", fontsize=8, color=cs.TEXT_2)
    ax.set_xlim(1, 5)
    ax.set_xlabel("Average star rating of reviews that mention the stage (1-5)")
    ax.grid(axis="y", visible=False)
    cs.title(fig, "Login, app speed and payment problems get the lowest ratings")
    cs.source_note(fig, "All 3 retailers, all ratings. Source: Google Play + App Store reviews (Ireland).")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(FIG / "m1_avg_rating_by_stage.png", dpi=160)


if __name__ == "__main__":
    main()
