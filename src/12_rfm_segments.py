"""Step 12: RFM segmentation (The Complete Journey, 84.51° release).

RFM = Recency, Frequency, Monetary.
- Recency:   days from the household's last trip to 1 Jan 2018 (lower = better)
- Frequency: number of baskets in 2017
- Monetary:  total spend in 2017 (USD)

Each measure gets a score from 1 to 5 (quintiles; 5 = best).
We then map score patterns to simple, named segments:
- Champions:        R >= 4 and F >= 4 and M >= 4
- Loyal:            F >= 4 (not Champions)
- Big spenders:     M >= 4 and F <= 3  (few trips, big baskets)
- Promising:        R >= 4 and F <= 3 and M <= 3
- Needs attention:  R = 3 (not in the groups above)
- At risk:          R <= 2 and F >= 3  (used to shop often, not recently)
- Lapsed / low:     everyone else (R <= 2, low F)

Profiles: size, spend share, AOV, coupon use, and demographics
(demographics exist for 801 households only).

Outputs
- data/processed/cj_households.parquet (one row per household, reused later)
- reports/m3_rfm_segments.csv
- reports/figures/m3_rfm_segments.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadr

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
SNAPSHOT = pd.Timestamp("2018-01-01")
ORDER = ["Champions", "Loyal", "Big spenders", "Promising", "Needs attention", "At risk", "Lapsed / low"]


def segment(r, f, m):
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if f >= 4:
        return "Loyal"
    if m >= 4 and f <= 3:
        return "Big spenders"
    if r >= 4:
        return "Promising"
    if r == 3:
        return "Needs attention"
    if f >= 3:
        return "At risk"
    return "Lapsed / low"


def main():
    b = pd.read_parquet(ROOT / "data/processed/cj_baskets.parquet")
    b = b[b["date"] < SNAPSHOT]
    h = b.groupby("household_id", observed=True).agg(
        last_trip=("date", "max"), frequency=("basket_id", "size"), monetary=("spend", "sum"),
        aov=("spend", "mean"), coupon_basket_share=("used_coupon", "mean"),
        coupon_disc_total=("coupon_disc", "sum"), active_weeks=("week", "nunique"),
    ).reset_index()
    h["recency_days"] = (SNAPSHOT - h["last_trip"]).dt.days

    # rank first so ties do not break the quintile cut
    h["R"] = pd.qcut(h["recency_days"].rank(method="first", ascending=False), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    h["F"] = pd.qcut(h["frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    h["M"] = pd.qcut(h["monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    h["segment"] = [segment(r, f, m) for r, f, m in zip(h["R"], h["F"], h["M"])]

    demo = next(iter(pyreadr.read_r(ROOT / "data/raw/completejourney/demographics.rda").values()))
    h = h.merge(demo, on="household_id", how="left")
    h.to_parquet(ROOT / "data/processed/cj_households.parquet", index=False)

    total = h["monetary"].sum()
    prof = h.groupby("segment").agg(
        households=("household_id", "size"),
        recency_days_median=("recency_days", "median"),
        baskets_median=("frequency", "median"),
        spend_median_usd=("monetary", "median"),
        aov_mean_usd=("aov", "mean"),
        coupon_basket_share_mean=("coupon_basket_share", "mean"),
        spend_sum=("monetary", "sum"),
        with_demographics=("age", lambda s: s.notna().sum()),
    ).reindex(ORDER)
    prof["share_households"] = prof["households"] / len(h)
    prof["share_spend"] = prof["spend_sum"] / total
    prof = prof.drop(columns="spend_sum")

    # demographic profile: most common age and income band (only households with data)
    d = h.dropna(subset=["age"])
    prof["top_age_band"] = d.groupby("segment")["age"].agg(lambda s: s.value_counts().idxmax())
    prof["share_with_kids"] = d.assign(kids=d["kids_count"].isin(["1", "2", "3+"])).groupby("segment")["kids"].mean()
    prof["share_income_50k_plus"] = d.assign(
        rich=~d["income"].isin(["Under 15K", "15-24K", "25-34K", "35-49K"])).groupby("segment")["rich"].mean()

    out = prof.round(3)
    out.to_csv(ROOT / "reports/m3_rfm_segments.csv")
    pd.set_option("display.width", 250)
    print(out.to_string())

    # ---- chart: share of households vs share of spend ----
    cs.apply()
    fig, ax = plt.subplots(figsize=(9, 4.8))
    y = np.arange(len(ORDER))
    hgt = 0.38
    ax.barh(y - hgt / 2, prof["share_households"] * 100, height=hgt - 0.04, color=cs.SERIES[0], label="Share of households")
    ax.barh(y + hgt / 2, prof["share_spend"] * 100, height=hgt - 0.04, color=cs.SERIES[1], label="Share of total spend")
    for yy, (a, s) in enumerate(zip(prof["share_households"] * 100, prof["share_spend"] * 100)):
        ax.text(a + 0.5, yy - hgt / 2, f"{a:.0f}%", va="center", fontsize=8, color=cs.TEXT_2)
        ax.text(s + 0.5, yy + hgt / 2, f"{s:.0f}%", va="center", fontsize=8, color=cs.TEXT_2)
    ax.set_yticks(y, [f"{s} (n={n})" for s, n in zip(ORDER, prof["households"])])
    ax.invert_yaxis()
    ax.set_xlabel("%")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    champ = prof.loc["Champions"]
    cs.title(fig, f"Champions are {champ.share_households:.0%} of households but "
                  f"{champ.share_spend:.0%} of spend")
    cs.source_note(fig, "RFM quintiles, 2017. The Complete Journey (84.51°), anonymised US retailer, not Tesco.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m3_rfm_segments.png", dpi=160)


if __name__ == "__main__":
    main()
