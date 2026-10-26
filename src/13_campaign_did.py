"""Step 13: Campaign uplift with difference-in-differences (DiD).

Question: did households that were sent a campaign spend more during the
campaign than they would have without it?

Design (for each of the 3 large "Type A" campaigns: 8, 13, 18)
- Treated group: households the retailer sent the campaign to.
- Control group: households NOT sent this campaign.
  Robustness check: control = households that got NO campaign in 2017.
- Pre period: the 8 weeks before the campaign starts.
- Post period: the weeks the campaign runs.
- Outcomes (USD per household per week; 0 if no purchase that week):
  1. total spend
  2. spend on the products covered by that campaign's coupons
     (more sensitive, because the campaign promotes these products)

Model (two-way fixed effects):
    spend_it = household_i + week_t + beta * (treated_i x post_t) + error
beta is the DiD uplift: extra weekly spend per treated household.
Standard errors are clustered by household.

Key assumption - PARALLEL TRENDS: without the campaign, treated and control
spend would have moved in parallel. We check the pre-period with an
"event study": treated x week effects for each pre week (should be about 0).

Limits: this is NOT a randomised experiment. The retailer chose who got the
campaign (likely its best customers), and other campaigns overlap in time.

Outputs: reports/m3_campaign_did.csv, reports/figures/m3_did_event_study.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyreadr
import statsmodels.api as sm

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
CAMPAIGNS = ["8", "13", "18"]
PRE_WEEKS = 8


def read(name):
    return next(iter(pyreadr.read_r(ROOT / "data/raw/completejourney" / name).values()))


def week_of(date, week_map):
    """Week number (1-53) used in the data for a given date."""
    d = pd.Timestamp(date)
    return int(week_map.loc[week_map.index <= d].iloc[-1]) if (week_map.index <= d).any() else 1


def two_way_demean(df, col):
    """Remove household and week means (works because the panel is balanced)."""
    return (df[col] - df.groupby("household_id")[col].transform("mean")
            - df.groupby("week")[col].transform("mean") + df[col].mean())


def run(camp, b, all_hh, week_map, desc, targets, never_targeted, control="not_this_campaign", outcome="total_spend"):
    row = desc[desc.campaign_id == camp].iloc[0]
    start_w = week_of(row.start_date, week_map)
    end_w = week_of(row.end_date, week_map)
    weeks = list(range(start_w - PRE_WEEKS, end_w + 1))
    treated = set(targets[targets.campaign_id == camp].household_id)
    if control == "not_this_campaign":
        hh = all_hh
    else:  # never targeted in 2017
        hh = sorted(treated | never_targeted)

    spend = b[b.week.isin(weeks) & b.household_id.isin(hh)].groupby(["household_id", "week"], observed=True)["spend"].sum()
    if outcome == "coupon_product_spend":
        lines = LINES[LINES.week.isin(weeks) & LINES.household_id.isin(hh)
                      & LINES.product_id.isin(COUPON_PRODUCTS[camp])]
        spend = lines.groupby(["household_id", "week"], observed=True)["sales_value"].sum().rename("spend")
    idx = pd.MultiIndex.from_product([hh, weeks], names=["household_id", "week"])
    p = spend.reindex(idx, fill_value=0).reset_index()
    p["treated"] = p["household_id"].isin(treated).astype(int)
    p["post"] = (p["week"] >= start_w).astype(int)
    p["did"] = p["treated"] * p["post"]

    # raw 2x2 means
    m = p.groupby(["treated", "post"])["spend"].mean().unstack()

    # TWFE DiD
    y = two_way_demean(p, "spend")
    x = two_way_demean(p, "did")
    fit = sm.OLS(y, x).fit(cov_type="cluster", cov_kwds={"groups": p["household_id"].astype(str).astype("category").cat.codes})
    beta, se = fit.params.iloc[0], fit.bse.iloc[0]
    lo, hi = fit.conf_int().iloc[0]

    # event study: treated x each week, week -1 (last pre week) is the reference
    rel = p["week"] - start_w
    es_cols = []
    for r in sorted(rel.unique()):
        if r == -1:
            continue
        c = f"rel_{r}"
        p[c] = ((rel == r) & (p["treated"] == 1)).astype(int)
        es_cols.append(c)
    X = pd.concat([two_way_demean(p, c).rename(c) for c in es_cols], axis=1)
    es = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": p["household_id"].astype(str).astype("category").cat.codes})
    pre_cols = [c for c in es_cols if int(c.split("_")[1]) < -1]
    wald = es.wald_test(np.eye(len(es_cols))[[es_cols.index(c) for c in pre_cols]], scalar=True)
    es_df = pd.DataFrame({"rel_week": [int(c.split("_")[1]) for c in es_cols],
                          "coef": es.params.values, "lo": es.conf_int()[0].values, "hi": es.conf_int()[1].values})
    es_df = pd.concat([es_df, pd.DataFrame([{"rel_week": -1, "coef": 0, "lo": 0, "hi": 0}])]).sort_values("rel_week")

    pre_treated_mean = m.loc[1, 0]
    result = {
        "campaign": camp, "outcome": outcome, "type": row.campaign_type, "start": row.start_date, "end": row.end_date,
        "control_group": control, "treated_hh": len(treated), "control_hh": len(hh) - len(treated),
        "post_weeks": end_w - start_w + 1,
        "treated_pre_mean": round(m.loc[1, 0], 2), "treated_post_mean": round(m.loc[1, 1], 2),
        "control_pre_mean": round(m.loc[0, 0], 2), "control_post_mean": round(m.loc[0, 1], 2),
        "did_usd_per_hh_week": round(beta, 2), "se": round(se, 2),
        "ci_low": round(lo, 2), "ci_high": round(hi, 2), "p_value": round(fit.pvalues.iloc[0], 4),
        "uplift_pct_of_treated_pre": round(beta / pre_treated_mean, 3),
        "pretrend_wald_p": round(float(wald.pvalue), 4),
    }
    return result, es_df


def main():
    b = pd.read_parquet(ROOT / "data/processed/cj_baskets.parquet")
    b = b[b["date"] < "2018-01-01"]
    week_map = b.groupby("date")["week"].min().sort_index()
    desc = read("campaign_descriptions.rda")
    targets = read("campaigns.rda")
    all_hh = sorted(b.household_id.unique())
    never = set(all_hh) - set(targets.household_id)
    print("Households never targeted by any campaign:", len(never))

    global LINES, COUPON_PRODUCTS
    LINES = pd.read_parquet(ROOT / "data/processed/cj_lines.parquet",
                            columns=["household_id", "week", "product_id", "sales_value"])
    coupons = read("coupons.rda")
    COUPON_PRODUCTS = {c: set(coupons.loc[coupons.campaign_id == c, "product_id"]) for c in CAMPAIGNS}
    for c in CAMPAIGNS:
        print(f"Campaign {c}: {len(COUPON_PRODUCTS[c]):,} products covered by its coupons")

    rows, events = [], {}
    for c in CAMPAIGNS:
        for outcome in ["total_spend", "coupon_product_spend"]:
            for control in ["not_this_campaign", "never_targeted"]:
                r, es = run(c, b, all_hh, week_map, desc, targets, never, control=control, outcome=outcome)
                rows.append(r)
                if control == "not_this_campaign":
                    events[(c, outcome)] = es
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "reports/m3_campaign_did.csv", index=False)
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))

    # ---- event study chart ----
    cs.apply()
    fig, axes = plt.subplots(2, 3, figsize=(12, 7.6), sharey="row")
    outcomes = [("total_spend", "Total spend"), ("coupon_product_spend", "Coupon-product spend")]
    for k, (outcome, label) in enumerate(outcomes):
        for ax, c in zip(axes[k], CAMPAIGNS):
            es = events[(c, outcome)]
            r = res[(res.campaign == c) & (res.control_group == "not_this_campaign")
                    & (res.outcome == outcome)].iloc[0]
            ax.axhline(0, color=cs.TEXT_2, lw=1)
            ax.axvline(-0.5, color=cs.GRID, lw=1.5, ls="--")
            ax.errorbar(es.rel_week, es.coef, yerr=[es.coef - es.lo, es.hi - es.coef], fmt="o",
                        color=cs.SERIES[0], ms=5, elinewidth=1.2, capsize=0)
            period = f"{pd.Timestamp(r.start):%d %b} - {pd.Timestamp(r.end):%d %b %Y}"
            ax.xaxis.set_major_locator(plt.MultipleLocator(2))
            ax.set_title(f"Campaign {c} ({period})\n"
                         f"DiD = ${r.did_usd_per_hh_week:.2f}/week [{r.ci_low:.2f}, {r.ci_high:.2f}], "
                         f"pre-trend p = {r.pretrend_wald_p:.2f}",
                         fontsize=8.5, loc="left", fontweight="normal")
            ax.grid(axis="x", visible=False)
            if k == 1:
                ax.set_xlabel("Weeks from campaign start")
        axes[k][0].set_ylabel(f"{label}:\ntreated minus control\n(USD/household/week, vs week -1)")
    cs.title(fig, "No campaign shows a clear spend lift: estimates during the campaign (right of the dashed line)\n"
                  "stay close to zero")
    cs.source_note(fig, "Dots = estimate, lines = 95% CI. Household + week fixed effects, SE clustered by household. "
                        "The Complete Journey (84.51°), not Tesco. Not a randomised test.")
    fig.tight_layout(rect=(0, 0.03, 1, 0.95))
    fig.savefig(FIG / "m3_did_event_study.png", dpi=160)


if __name__ == "__main__":
    main()
