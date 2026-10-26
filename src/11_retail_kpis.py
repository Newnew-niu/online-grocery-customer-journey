"""Step 11: Retail KPIs and retention (The Complete Journey, 84.51° release).

KPIs
- AOV (average order value) = average spend per basket
- Items per basket
- Purchase frequency = baskets per household in the year
- Inter-purchase time = days between two shopping trips of the same household

Retention
- Monthly active rate: share of households that shop in each month.
- Cohort table: households grouped by the month of their first trip;
  for each later month, the share still shopping.
  Note: this panel only includes households that shopped often, so most
  households start in January. We report this honestly.

Outputs
- reports/m3_kpis.csv, reports/m3_cohort_retention.csv
- reports/figures/m3_monthly_active.png, reports/figures/m3_cohort_retention.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"


def main():
    b = pd.read_parquet(ROOT / "data/processed/cj_baskets.parquet")
    b = b[b["date"] < "2018-01-01"]  # keep calendar year 2017 only
    hh = b.groupby("household_id", observed=True)

    b = b.sort_values(["household_id", "date"])
    trip_days = b.groupby(["household_id", "date"], observed=True).size().reset_index()[["household_id", "date"]]
    trip_days["gap"] = trip_days.groupby("household_id", observed=True)["date"].diff().dt.days

    kpis = {
        "households": b["household_id"].nunique(),
        "baskets": len(b),
        "total_spend_usd": round(b["spend"].sum(), 0),
        "aov_usd_mean": round(b["spend"].mean(), 2),
        "aov_usd_median": round(b["spend"].median(), 2),
        "items_per_basket_mean": round(b["items"].mean(), 2),
        "items_per_basket_median": float(b["items"].median()),
        "baskets_per_household_mean": round(hh.size().mean(), 1),
        "baskets_per_household_median": float(hh.size().median()),
        "spend_per_household_mean_usd": round(hh["spend"].sum().mean(), 0),
        "inter_purchase_days_median": float(trip_days["gap"].median()),
        "inter_purchase_days_mean": round(trip_days["gap"].mean(), 1),
        "share_baskets_with_coupon": round(b["used_coupon"].mean(), 4),
        "share_households_ever_coupon": round(hh["used_coupon"].max().mean(), 3),
    }
    k = pd.DataFrame(list(kpis.items()), columns=["kpi", "value"])
    k.to_csv(ROOT / "reports/m3_kpis.csv", index=False)
    print(k.to_string(index=False))

    # ---- retention ----
    b["month"] = b["date"].dt.to_period("M")
    active = b.groupby("month")["household_id"].nunique()
    n_hh = b["household_id"].nunique()
    monthly = (active / n_hh).rename("share_active")
    print("\nShare of households active each month:\n", monthly.round(3).to_string())

    first = b.groupby("household_id", observed=True)["month"].min().rename("cohort")
    m = b[["household_id", "month"]].drop_duplicates().join(first, on="household_id")
    m["age"] = (m["month"] - m["cohort"]).apply(lambda x: x.n)
    sizes = first.value_counts().sort_index()
    cohort = m.groupby(["cohort", "age"])["household_id"].nunique().unstack()
    cohort = cohort.div(sizes, axis=0)
    cohort.insert(0, "cohort_size", sizes)
    cohort.round(3).to_csv(ROOT / "reports/m3_cohort_retention.csv")
    print("\nCohort sizes (month of first trip):\n", sizes.to_string())

    # how many households stop shopping? last trip before November
    last = b.groupby("household_id", observed=True)["date"].max()
    lapsed = (last < "2017-11-01").mean()
    print(f"\nHouseholds whose last trip was before 1 Nov 2017 (lapsed): {lapsed:.1%}")
    with open(ROOT / "reports/m3_kpis.csv", "a") as f:
        f.write(f"share_households_lapsed_before_nov,{round(lapsed, 3)}\n")

    # ---- charts ----
    cs.apply()
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(monthly))
    ax.plot(x, monthly.values * 100, color=cs.SERIES[0], lw=2, marker="o", ms=5)
    ax.set_xticks(x, [p.strftime("%b") for p in monthly.index])
    ax.set_ylim(0, 100)
    ax.set_ylabel("Households that shopped in the month (%)")
    for xi, v in zip([0, len(x) - 1], [monthly.values[0], monthly.values[-1]]):
        ax.annotate(f"{v:.0%}", (xi, v * 100), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=9, color=cs.TEXT_2)
    cs.title(fig, "Monthly active households stay high all year (2017)")
    cs.source_note(fig, f"The Complete Journey (84.51°), {n_hh:,} households. Anonymised US retailer, not Tesco.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m3_monthly_active.png", dpi=160)

    big = cohort[cohort["cohort_size"] >= 30].drop(columns="cohort_size")
    fig, ax = plt.subplots(figsize=(9, 0.6 * len(big) + 1.8))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#cde2fb", "#104281"])
    ax.imshow(big.values, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(big.shape[0]):
        for j in range(big.shape[1]):
            v = big.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=7.5,
                        color="white" if v > 0.6 else cs.TEXT)
    ax.set_xticks(range(big.shape[1]), [f"+{a}" for a in big.columns])
    ax.set_yticks(range(big.shape[0]), [f"{c.strftime('%b')} (n={sizes[c]})" for c in big.index])
    ax.set_xlabel("Months after first trip")
    ax.grid(False)
    cs.title(fig, "Households that started later shop less steadily: about 88% of the January\n"
                  "cohort shop each month, against 50-70% of later cohorts")
    cs.source_note(fig, "Cohorts with 30+ households. The Complete Journey (84.51°). Not Tesco data.")
    fig.tight_layout(rect=(0, 0.05, 1, 0.92))
    fig.savefig(FIG / "m3_cohort_retention.png", dpi=160)


if __name__ == "__main__":
    main()
