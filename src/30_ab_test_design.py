"""Step 30: A/B test design - sample size, power and duration.

Test: add one-tap wallet payment (Apple Pay / Google Pay) on the payment step.
Hypothesis comes from Module 1 (checkout & payment complaints).
Baselines come from Module 2 (GA4 public sample, Google Merchandise Store).
This test is DESIGNED, not run.

Unit of randomisation: user (so a person always sees the same version).
Primary metric: share of users who reach the payment step and then purchase
(within the test period). Only users who reach the payment step are analysed
("triggered" analysis), because the change is only visible there.

Outputs: reports/m4_power_table.csv, reports/m4_design_numbers.json,
         reports/figures/m4_power_curve.png
"""
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
ALPHA, POWER = 0.05, 0.80
DAYS = 92  # 1 Nov 2020 - 31 Jan 2021


def n_per_group(p0, p1, alpha=ALPHA, power=POWER):
    h = proportion_effectsize(p1, p0)
    return math.ceil(NormalIndPower().solve_power(effect_size=h, alpha=alpha, power=power,
                                                  ratio=1.0, alternative="two-sided"))


def main():
    d = pd.read_parquet(ROOT / "data/raw/ga4/ga4_sessions.parquet")

    # user-level baseline: users who reached add_payment_info at least once,
    # and whether they purchased in a session at or after that point
    d = d.sort_values(["user_pseudo_id", "session_date", "ga_session_id"])
    pay = d[d.add_payment_info == 1].groupby("user_pseudo_id").agg(first_pay=("ga_session_id", "min"))
    x = d.merge(pay, on="user_pseudo_id")
    bought = x[(x.ga_session_id >= x.first_pay) & (x.purchase == 1)].user_pseudo_id.unique()
    users_pay = len(pay)
    p0_user = len(bought) / users_pay
    users_pay_week = users_pay / (DAYS / 7)
    sessions = len(d)
    p0_session = ((d.add_payment_info == 1) & (d.purchase == 1)).sum() / (d.add_payment_info == 1).sum()
    p0_overall = (d.purchase == 1).mean()
    users_week = d.user_pseudo_id.nunique() / (DAYS / 7)
    print(f"Users who reached payment step: {users_pay:,} ({users_pay_week:.0f} per week)")
    print(f"User-level payment -> purchase baseline: {p0_user:.4f}")
    print(f"Session-level payment -> purchase baseline: {p0_session:.4f}")

    # power table for different minimum detectable effects (absolute points)
    rows = []
    for mde in [0.02, 0.03, 0.04, 0.05]:
        p1 = p0_user + mde
        n = n_per_group(p0_user, p1)
        weeks = math.ceil(2 * n / users_pay_week)
        rows.append({"metric": "payment -> purchase (triggered users)", "baseline": p0_user,
                     "mde_abs_points": mde * 100, "mde_relative": mde / p0_user, "target": p1,
                     "n_per_group": n, "n_total": 2 * n, "weeks_needed": weeks})
    # comparison: same absolute business gain measured on ALL users (diluted)
    extra_buyers_share = 0.03 * users_pay / d.user_pseudo_id.nunique()  # +3 pts on triggered users
    p0_all_users = d.groupby("user_pseudo_id")["purchase"].max().mean()
    n_diluted = n_per_group(p0_all_users, p0_all_users + extra_buyers_share)
    rows.append({"metric": "purchase, ALL users (not triggered) - same +3pt gain diluted",
                 "baseline": p0_all_users, "mde_abs_points": extra_buyers_share * 100,
                 "mde_relative": extra_buyers_share / p0_all_users, "target": p0_all_users + extra_buyers_share,
                 "n_per_group": n_diluted, "n_total": 2 * n_diluted,
                 "weeks_needed": math.ceil(2 * n_diluted / users_week)})
    t = pd.DataFrame(rows)
    t.round(4).to_csv(ROOT / "reports/m4_power_table.csv", index=False)
    pd.set_option("display.width", 220)
    print(t.round(4).to_string(index=False))

    chosen = t.iloc[1]  # +3 points
    design = {
        "baseline_user_payment_to_purchase": round(p0_user, 4),
        "baseline_session_payment_to_purchase": round(p0_session, 4),
        "baseline_overall_session_conversion": round(p0_overall, 4),
        "users_reaching_payment_per_week": round(users_pay_week, 1),
        "alpha": ALPHA, "power": POWER,
        "mde_abs_points": 3.0, "mde_relative": round(chosen.mde_relative, 4),
        "n_per_group": int(chosen.n_per_group), "n_total": int(chosen.n_total),
        "weeks_at_ga4_traffic": int(chosen.weeks_needed),
        "planned_weeks": max(int(chosen.weeks_needed), 2),
    }
    (ROOT / "reports/m4_design_numbers.json").write_text(json.dumps(design, indent=2))
    print(json.dumps(design, indent=1))

    # power curve
    cs.apply()
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    ns = np.arange(200, 12001, 100)
    for mde, color in zip([0.02, 0.03, 0.05], cs.SERIES[:3]):
        h = proportion_effectsize(p0_user + mde, p0_user)
        pw = NormalIndPower().power(effect_size=h, nobs1=ns, alpha=ALPHA, ratio=1.0)
        ax.plot(ns, pw * 100, color=color, lw=2, label=f"+{mde * 100:.0f} pts ({p0_user:.1%} -> {p0_user + mde:.1%})")
    ax.axhline(80, color=cs.TEXT_2, lw=1, ls="--")
    ax.axvline(design["n_per_group"], color=cs.SERIES[1], lw=1, ls=":")
    ax.text(design["n_per_group"] + 120, 20, f"{design['n_per_group']:,} users per group\nfor +3 pts at 80% power",
            fontsize=8.5, color=cs.TEXT_2)
    ax.set_xlabel("Users per group (who reach the payment step)")
    ax.set_ylabel("Power (%)")
    ax.set_ylim(0, 100)
    ax.legend(title="True effect", title_fontsize=9, loc="lower right")
    cs.title(fig, f"About {design['n_per_group']:,} users per group are needed to detect +3 points "
                  "with 80% power")
    cs.source_note(fig, "Two-sided test, alpha = 0.05. Baseline from GA4 public sample (Google Merchandise Store). "
                        "Designed, not run.")
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m4_power_curve.png", dpi=160)


if __name__ == "__main__":
    main()
