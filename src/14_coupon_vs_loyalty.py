"""Step 14: Are heavy coupon users less loyal?

Background: an earlier project (github.com/Newnew-niu/ecommerce-repeat-purchase-analysis)
found on SIMULATED data that coupon-dependent customers repeat less.
Here we test the same idea on REAL data (The Complete Journey, 84.51° release).

Design (to avoid a circular result)
- Coupon dependency is measured in the FIRST half of 2017 (Jan-Jun):
  share of a household's baskets that used a coupon (coupon_disc > 0).
- Loyalty is measured in the SECOND half (Jul-Dec):
  1. number of baskets in H2
  2. share of H2 weeks with at least one trip
  3. lapsed = no trip in the last 3 months (Oct-Dec)
- Only households that shopped in H1 are included.
- Heavy shoppers have more chances to use coupons, so the regressions
  control for H1 baskets and H1 spend.

Groups (based on H1 coupon basket share):
- No coupons: 0
- Light: above 0, up to the median of coupon users
- Medium: median to 75th percentile
- Heavy: top 25% of coupon users

Outputs: reports/m3_coupon_loyalty_groups.csv, reports/m3_coupon_loyalty_models.txt,
         reports/figures/m3_coupon_vs_loyalty.png
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
GROUPS = ["No coupons", "Light", "Medium", "Heavy"]


def main():
    b = pd.read_parquet(ROOT / "data/processed/cj_baskets.parquet")
    b = b[b["date"] < "2018-01-01"]
    h1 = b[b["date"] < "2017-07-01"]
    h2 = b[b["date"] >= "2017-07-01"]
    h2_weeks = h2["week"].nunique()

    a = h1.groupby("household_id", observed=True).agg(
        h1_baskets=("basket_id", "size"), h1_spend=("spend", "sum"),
        h1_coupon_share=("used_coupon", "mean"),
        h1_coupon_savings_share=("coupon_disc", "sum"))
    a["h1_coupon_savings_share"] = a["h1_coupon_savings_share"] / a["h1_spend"]
    z = h2.groupby("household_id", observed=True).agg(h2_baskets=("basket_id", "size"),
                                                      h2_weeks=("week", "nunique"))
    last = b.groupby("household_id", observed=True)["date"].max()
    d = a.join(z).fillna({"h2_baskets": 0, "h2_weeks": 0})
    d["h2_active_week_share"] = d["h2_weeks"] / h2_weeks
    d["lapsed"] = (last.reindex(d.index) < "2017-10-01").astype(int)

    users = d.loc[d["h1_coupon_share"] > 0, "h1_coupon_share"]
    q50, q75 = users.quantile([0.5, 0.75])
    d["group"] = np.select(
        [d["h1_coupon_share"] == 0, d["h1_coupon_share"] <= q50, d["h1_coupon_share"] <= q75],
        GROUPS[:3], default="Heavy")
    print(f"Households in H1: {len(d):,}. Coupon users: {len(users):,} ({len(users)/len(d):.1%}).")
    print(f"Cut points (share of baskets with a coupon): median {q50:.3f}, 75th pct {q75:.3f}")

    g = d.groupby("group").agg(
        households=("h1_baskets", "size"),
        h1_coupon_share_mean=("h1_coupon_share", "mean"),
        h1_baskets_median=("h1_baskets", "median"),
        h1_spend_median=("h1_spend", "median"),
        h2_baskets_median=("h2_baskets", "median"),
        h2_active_week_share_mean=("h2_active_week_share", "mean"),
        lapsed_rate=("lapsed", "mean"),
    ).reindex(GROUPS)
    g["h2_to_h1_baskets_ratio_median"] = d.assign(r=d.h2_baskets / d.h1_baskets).groupby("group")["r"].median().reindex(GROUPS)
    g.round(3).to_csv(ROOT / "reports/m3_coupon_loyalty_groups.csv")
    pd.set_option("display.width", 250)
    print(g.round(3).to_string())

    # ---- tests ----
    lines = []
    kw = stats.kruskal(*[d.loc[d.group == k, "h2_active_week_share"] for k in GROUPS])
    lines.append(f"Kruskal-Wallis test, H2 active-week share across 4 groups: H={kw.statistic:.1f}, p={kw.pvalue:.2g}")
    rho = stats.spearmanr(d.loc[d.h1_coupon_share > 0, "h1_coupon_share"],
                          d.loc[d.h1_coupon_share > 0, "h2_active_week_share"])
    lines.append(f"Spearman correlation (coupon users only), coupon share vs H2 active-week share: "
                 f"rho={rho.correlation:.3f}, p={rho.pvalue:.2g}")

    d["log_h1_baskets"] = np.log(d["h1_baskets"])
    d["log_h1_spend"] = np.log1p(d["h1_spend"])
    d["log_h2_baskets"] = np.log1p(d["h2_baskets"])
    d["coupon_share_10pt"] = d["h1_coupon_share"] * 10  # effect per +10 percentage points

    m1 = smf.ols("log_h2_baskets ~ coupon_share_10pt + log_h1_baskets + log_h1_spend", data=d).fit(cov_type="HC1")
    m2 = smf.ols("h2_active_week_share ~ coupon_share_10pt + log_h1_baskets + log_h1_spend", data=d).fit(cov_type="HC1")
    m3 = smf.logit("lapsed ~ coupon_share_10pt + log_h1_baskets + log_h1_spend", data=d).fit(disp=0)
    m4 = smf.ols("h2_active_week_share ~ C(group, Treatment('No coupons')) + log_h1_baskets + log_h1_spend",
                 data=d).fit(cov_type="HC1")

    def row(m, name, var="coupon_share_10pt"):
        ci = m.conf_int().loc[var]
        return f"{name}: coef={m.params[var]:.4f} [95% CI {ci[0]:.4f}, {ci[1]:.4f}], p={m.pvalues[var]:.3g}"

    lines.append("")
    lines.append("Effect of +10 percentage points in H1 coupon basket share, controlling for H1 baskets and spend:")
    lines.append(row(m1, "  log(1 + H2 baskets) [OLS]"))
    lines.append(row(m2, "  H2 active-week share [OLS]"))
    lines.append(row(m3, "  lapsed (log-odds) [logit]"))
    or_ = np.exp(m3.params["coupon_share_10pt"])
    lines.append(f"  -> odds ratio for lapsing per +10 pts: {or_:.3f}")
    lines.append("")
    lines.append("Groups vs 'No coupons' (H2 active-week share, same controls):")
    for k in GROUPS[1:]:
        v = f"C(group, Treatment('No coupons'))[T.{k}]"
        ci = m4.conf_int().loc[v]
        lines.append(f"  {k}: {m4.params[v]:+.4f} [{ci[0]:+.4f}, {ci[1]:+.4f}], p={m4.pvalues[v]:.3g}")
    lines.append(f"\nN = {len(d)} households. Robust (HC1) standard errors for OLS.")
    text = "\n".join(lines)
    print("\n" + text)
    (ROOT / "reports/m3_coupon_loyalty_models.txt").write_text(
        text + "\n\n" + m1.summary().as_text() + "\n\n" + m2.summary().as_text() + "\n\n" + m3.summary().as_text(),
        encoding="utf-8")

    # ---- chart: H2 active-week share and lapse rate by group, with 95% CI ----
    cs.apply()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for ax, col, lab in [(axes[0], "h2_active_week_share", "Share of weeks with a trip, Jul-Dec (%)"),
                         (axes[1], "lapsed", "Lapsed: no trip Oct-Dec (%)")]:
        means = d.groupby("group")[col].mean().reindex(GROUPS) * 100
        se = d.groupby("group")[col].sem().reindex(GROUPS) * 100
        x = np.arange(len(GROUPS))
        ax.bar(x, means, color=cs.SERIES[0], width=0.6)
        ax.errorbar(x, means, yerr=1.96 * se, fmt="none", ecolor=cs.TEXT_2, elinewidth=1.2)
        for xi, v in zip(x, means):
            ax.text(xi + 0.08, v + 1, f"{v:.0f}%", fontsize=8.5, color=cs.TEXT_2, ha="left")
        ax.set_xticks(x, [f"{k}\n(n={n})" for k, n in zip(GROUPS, g["households"])])
        ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False)
    cs.title(fig, "Coupon users are more loyal than non-users. Heavy users look less active than light users,\n"
                  "but that gap disappears once we control for how often they shopped in Jan-Jun")
    cs.source_note(fig, "Coupon use measured Jan-Jun 2017, loyalty Jul-Dec 2017. Bars = mean, lines = 95% CI. "
                        "The Complete Journey (84.51°), not Tesco.")
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(FIG / "m3_coupon_vs_loyalty.png", dpi=160)


if __name__ == "__main__":
    main()
