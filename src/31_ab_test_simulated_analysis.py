"""Step 31: SIMULATED example of how the A/B test would be analysed.

!!! These numbers are SIMULATED. The test was designed, not run. !!!
This shows the analysis steps only. Do not quote these results as findings.

Setup of the simulation
- 2,959 users per group (from step 30).
- Control purchase rate after reaching payment = 76.8% (real GA4 baseline).
- Treatment: we ASSUME a true +3 point lift (79.8%).
- Order values are drawn from real GA4 purchase revenues (resampled), with
  no true change between groups (to show a guardrail check).
- Random seed fixed, so the result is repeatable.

Analysis steps
1. Sample ratio mismatch (SRM) check - is the 50/50 split OK?
2. Primary metric: two-proportion z-test + 95% CI for the difference.
3. Guardrail: AOV, Welch t-test (should not drop by more than 2%).
4. Decision using the pre-registered rules.

Output: reports/m4_simulated_analysis.txt
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.proportion import confint_proportions_2indep, proportions_ztest

ROOT = Path(__file__).resolve().parents[1]
rng = np.random.default_rng(2026)


def main():
    des = json.loads((ROOT / "reports/m4_design_numbers.json").read_text())
    n = des["n_per_group"]
    p0 = des["baseline_user_payment_to_purchase"]
    p1 = p0 + 0.03

    # assignment with a tiny random imbalance, like real traffic
    total = 2 * n
    n_a = rng.binomial(total, 0.5)
    n_b = total - n_a
    buy_a = rng.binomial(1, p0, n_a)
    buy_b = rng.binomial(1, p1, n_b)

    d = pd.read_parquet(ROOT / "data/raw/ga4/ga4_sessions.parquet")
    rev = d.loc[(d.purchase == 1) & (d.revenue_usd > 0), "revenue_usd"] / \
        d.loc[(d.purchase == 1) & (d.revenue_usd > 0), "purchase_events"]
    aov_a = rng.choice(rev.values, buy_a.sum())
    aov_b = rng.choice(rev.values, buy_b.sum())

    lines = ["SIMULATED A/B TEST ANALYSIS - NOT REAL RESULTS", "=" * 48, ""]
    srm = stats.chisquare([n_a, n_b])
    lines.append(f"1. SRM check: control {n_a:,} vs treatment {n_b:,} users; chi-square p = {srm.pvalue:.3f}"
                 f" -> {'OK' if srm.pvalue >= 0.001 else 'STOP: allocation problem'}")

    z, p = proportions_ztest([buy_b.sum(), buy_a.sum()], [n_b, n_a])
    lo, hi = confint_proportions_2indep(buy_b.sum(), n_b, buy_a.sum(), n_a, method="wald")
    ra, rb = buy_a.mean(), buy_b.mean()
    lines.append(f"2. Primary metric (payment -> purchase): control {ra:.2%}, treatment {rb:.2%}")
    lines.append(f"   difference = {(rb - ra) * 100:+.2f} pts, 95% CI [{lo * 100:+.2f}, {hi * 100:+.2f}], "
                 f"z = {z:.2f}, p = {p:.4f}")

    t, pt = stats.ttest_ind(aov_b, aov_a, equal_var=False)
    change = aov_b.mean() / aov_a.mean() - 1
    lines.append(f"3. Guardrail AOV: control ${aov_a.mean():.2f}, treatment ${aov_b.mean():.2f} "
                 f"({change:+.1%}); Welch t-test p = {pt:.3f}")

    ship = (p < 0.05) and (lo > 0) and (change > -0.02 or pt >= 0.05)
    lines.append("4. Decision (pre-registered rules): " + (
        "SHIP - primary metric up and significant, guardrail not harmed." if ship else
        "DO NOT SHIP / keep testing - rules not met."))
    # repeat the whole test many times: how often do we detect the true +3 pts?
    reps = 2000
    a = rng.binomial(n, p0, reps)
    b = rng.binomial(n, p1, reps)
    pooled = (a + b) / (2 * n)
    zz = (b - a) / n / np.sqrt(pooled * (1 - pooled) * 2 / n)
    detected = (np.abs(zz) > 1.96) & (zz > 0)
    lines.append("")
    lines.append(f"5. Repeat check: in {reps:,} simulated tests with a true +3 pt lift, "
                 f"{detected.mean():.1%} were significant (planned power: 80%).")
    lines.append("   So about 1 test in 5 misses a real effect of this size. The single run above is one of")
    lines.append("   those misses if it is not significant - this is why we fix the sample size in advance")
    lines.append("   and do not stop early or re-run until we get the answer we want.")
    lines.append("")
    lines.append(f"Simulation inputs: n per group = {n:,}, control rate = {p0:.2%} (real GA4 baseline), "
                 f"assumed true lift = +3.0 pts, seed = 2026.")
    text = "\n".join(lines)
    (ROOT / "reports/m4_simulated_analysis.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
