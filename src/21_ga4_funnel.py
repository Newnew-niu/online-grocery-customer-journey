"""Step 21: Funnel, conversion and cart abandonment from GA4 sessions.

Data: GA4 public sample, Google Merchandise Store (real e-commerce web
analytics data; it sells Google-branded products, NOT groceries),
1 Nov 2020 - 31 Jan 2021. Built by sql/01_session_funnel.sql.

Funnel steps (per session):
    view_item -> add_to_cart -> begin_checkout -> add_payment_info -> purchase

Two views
- Closed funnel: a session counts at a step only if it ALSO did every earlier
  step in the same session. This is the main view.
- Open funnel: any session with the event. Shown because 2,000 purchasing
  sessions have no add_to_cart in the same session (the basket was likely
  filled in an earlier session).

Definitions
- Step conversion = sessions at step k / sessions at step k-1
- Overall conversion = purchasing sessions / all sessions
- Cart abandonment = share of sessions with add_to_cart that do NOT purchase
- AOV = purchase revenue / number of purchase events
  (purchases with $0 revenue are removed; they come from data obfuscation)

Segments: device, first-touch medium (how the user was first acquired),
new vs returning session. 95% CIs use the Wilson method.

Outputs: reports/m2_funnel_overall.csv, reports/m2_funnel_segments.csv,
         reports/m2_baselines.json (used by Module 4), figures.
"""
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from statsmodels.stats.proportion import proportion_confint

import chart_style as cs

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "reports" / "figures"
STEPS = ["view_item", "add_to_cart", "begin_checkout", "add_payment_info", "purchase"]
LABELS = ["View item", "Add to cart", "Begin checkout", "Add payment info", "Purchase"]
SOURCE = "GA4 public sample (Google Merchandise Store, not grocery), 1 Nov 2020 - 31 Jan 2021."


def closed_flags(d):
    f = pd.DataFrame(index=d.index)
    ok = pd.Series(True, index=d.index)
    for s in STEPS:
        ok = ok & (d[s] == 1)
        f[s] = ok.astype(int)
    return f


def funnel_table(d, closed=True):
    f = closed_flags(d) if closed else d[STEPS]
    n = len(d)
    counts = f.sum()
    rows = []
    for i, s in enumerate(STEPS):
        prev = n if i == 0 else counts[STEPS[i - 1]]
        rows.append({"step": s, "sessions": int(counts[s]), "share_of_all_sessions": counts[s] / n,
                     "step_conversion": counts[s] / prev if prev else np.nan})
    return pd.DataFrame(rows)


def seg_metrics(d, col):
    out = []
    for k, g in d.groupby(col):
        f = closed_flags(g)
        n = len(g)
        carts = (g["add_to_cart"] == 1).sum()
        cart_purch = ((g["add_to_cart"] == 1) & (g["purchase"] == 1)).sum()
        pay = (g["add_payment_info"] == 1).sum()
        pay_purch = ((g["add_payment_info"] == 1) & (g["purchase"] == 1)).sum()
        buy = (g["purchase"] == 1).sum()
        lo, hi = proportion_confint(buy, n, method="wilson")
        rev = g.loc[g.revenue_usd > 0]
        out.append({
            "segment_type": col, "segment": k, "sessions": n, "share_of_sessions": n / len(d),
            "view_rate": g["view_item"].mean(),
            "view_to_cart": f["add_to_cart"].sum() / max(f["view_item"].sum(), 1),
            "cart_to_checkout": f["begin_checkout"].sum() / max(f["add_to_cart"].sum(), 1),
            "checkout_to_payment": f["add_payment_info"].sum() / max(f["begin_checkout"].sum(), 1),
            "payment_to_purchase_closed": f["purchase"].sum() / max(f["add_payment_info"].sum(), 1),
            "payment_to_purchase_open": pay_purch / max(pay, 1),
            "conversion_rate": buy / n, "conversion_ci_low": lo, "conversion_ci_high": hi,
            "cart_abandonment": 1 - cart_purch / max(carts, 1),
            "aov_usd": rev["revenue_usd"].sum() / max(rev["purchase_events"].sum(), 1),
        })
    return pd.DataFrame(out)


def main():
    d = pd.read_parquet(ROOT / "data/raw/ga4/ga4_sessions.parquet")
    d["user_type"] = np.where(d["session_number"] == 1, "New", "Returning")
    keep = ["organic", "(none)", "referral", "cpc"]
    d["medium"] = d["first_medium"].where(d["first_medium"].isin(keep), "Other / hidden")
    d["medium"] = d["medium"].replace({"(none)": "direct (none)"})

    closed = funnel_table(d, closed=True)
    opened = funnel_table(d, closed=False)
    both = closed.merge(opened, on="step", suffixes=("_closed", "_open"))
    both.round(4).to_csv(ROOT / "reports/m2_funnel_overall.csv", index=False)
    print(f"Sessions: {len(d):,}  Users: {d.user_pseudo_id.nunique():,}")
    print(both.round(4).to_string(index=False))

    carts = (d.add_to_cart == 1).sum()
    cart_purch = ((d.add_to_cart == 1) & (d.purchase == 1)).sum()
    pay = (d.add_payment_info == 1).sum()
    pay_purch = ((d.add_payment_info == 1) & (d.purchase == 1)).sum()
    checkout = (d.begin_checkout == 1).sum()
    checkout_purch = ((d.begin_checkout == 1) & (d.purchase == 1)).sum()
    rev = d[d.revenue_usd > 0]
    base = {
        "sessions": int(len(d)), "users": int(d.user_pseudo_id.nunique()),
        "purchasing_sessions": int((d.purchase == 1).sum()),
        "overall_conversion": float((d.purchase == 1).mean()),
        "cart_abandonment": float(1 - cart_purch / carts),
        "checkout_abandonment": float(1 - checkout_purch / checkout),
        "payment_to_purchase": float(pay_purch / pay),
        "sessions_with_payment_info": int(pay),
        "sessions_with_payment_info_per_week": float(pay / 13.1),  # 92 days = 13.1 weeks
        "sessions_per_week": float(len(d) / 13.1),
        "aov_usd": float(rev.revenue_usd.sum() / rev.purchase_events.sum()),
        "purchases_with_zero_revenue_removed": int(((d.purchase == 1) & (d.revenue_usd == 0)).sum()),
        "purchases_without_add_to_cart_in_session": int(((d.purchase == 1) & (d.add_to_cart == 0)).sum()),
    }
    (ROOT / "reports/m2_baselines.json").write_text(json.dumps(base, indent=2))
    print("\nBaselines:", json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in base.items()}, indent=1))

    seg = pd.concat([seg_metrics(d, c) for c in ["device_category", "medium", "user_type"]], ignore_index=True)
    seg.round(4).to_csv(ROOT / "reports/m2_funnel_segments.csv", index=False)
    pd.set_option("display.width", 250)
    print("\n", seg.round(3).to_string(index=False))

    print("\nChi-square tests (conversion differs by segment?):")
    for c in ["device_category", "medium", "user_type"]:
        ct = pd.crosstab(d[c] if c != "medium" else d["medium"], d["purchase"])
        chi2, p, dof, _ = chi2_contingency(ct)
        print(f"  {c}: chi2={chi2:.1f}, dof={dof}, p={p:.2g}")
    # payment -> purchase by device (relevant for Module 4)
    sub = d[d.add_payment_info == 1]
    ct = pd.crosstab(sub["device_category"], sub["purchase"])
    chi2, p, dof, _ = chi2_contingency(ct)
    print(f"  payment->purchase by device: chi2={chi2:.1f}, dof={dof}, p={p:.2g}")

    # ---- chart 1: closed funnel ----
    cs.apply()
    fig, ax = plt.subplots(figsize=(9, 4.6))
    y = np.arange(len(STEPS))[::-1]
    vals = closed["sessions"].values
    ax.barh(y, vals, color=cs.SERIES[0], height=0.62)
    for yy, v, sc, sh in zip(y, vals, closed["step_conversion"], closed["share_of_all_sessions"]):
        txt = f"{v:,}  ({sh:.1%} of sessions)"
        ax.text(v + vals.max() * 0.01, yy, txt, va="center", fontsize=8.5, color=cs.TEXT_2)
    for i in range(1, len(STEPS)):
        sc = closed["step_conversion"].iloc[i]
        ax.text(vals.max() * 0.55, y[i] + 0.5, f"step conversion {sc:.0%}  (drop {1 - sc:.0%})",
                va="center", fontsize=8, color=cs.TEXT, ha="left",
                fontweight="bold" if i == closed["step_conversion"].iloc[1:].idxmin() else "normal")
    ax.set_yticks(y, LABELS)
    ax.set_xlim(0, vals.max() * 1.45)
    ax.set_xlabel("Sessions (closed funnel: every earlier step done in the same session)")
    ax.grid(axis="y", visible=False)
    worst = closed["step_conversion"].iloc[1:].idxmin()
    cs.title(fig, f"Biggest drop: {LABELS[worst - 1]} -> {LABELS[worst]} "
                  f"(only {closed['step_conversion'].iloc[worst]:.0%} continue)")
    cs.source_note(fig, f"{len(d):,} sessions. " + SOURCE)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m2_funnel.png", dpi=160)

    # ---- chart 2: step conversion by device ----
    dev = seg[seg.segment_type == "device_category"].set_index("segment").loc[["desktop", "mobile", "tablet"]]
    cols = ["view_to_cart", "cart_to_checkout", "checkout_to_payment", "payment_to_purchase_closed"]
    names = ["View -> cart", "Cart -> checkout", "Checkout -> payment", "Payment -> purchase"]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    x = np.arange(len(cols))
    w = 0.26
    for i, (k, color) in enumerate(zip(dev.index, cs.SERIES[:3])):
        v = dev.loc[k, cols].values.astype(float) * 100
        ax.bar(x + (i - 1) * w, v, width=w - 0.03, color=color, label=f"{k} (n={dev.loc[k, 'sessions']:,})")
        for xx, vv in zip(x + (i - 1) * w, v):
            ax.text(xx, vv + 1, f"{vv:.0f}", ha="center", fontsize=7.5, color=cs.TEXT_2)
    ax.set_xticks(x, names)
    ax.set_ylabel("Step conversion (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", title="Device", title_fontsize=9)
    cs.title(fig, "Step conversion is similar across devices; view -> cart is the weak step for all")
    cs.source_note(fig, "Closed funnel. " + SOURCE)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m2_step_conversion_by_device.png", dpi=160)

    # ---- chart 3: conversion rate by segment with CI ----
    order = [("device_category", ["desktop", "mobile", "tablet"]),
             ("user_type", ["New", "Returning"]),
             ("medium", ["organic", "direct (none)", "referral", "cpc", "Other / hidden"])]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    labels, yy, i = [], [], 0
    for t, ks in order:
        for k in ks:
            r = seg[(seg.segment_type == t) & (seg.segment == k)].iloc[0]
            ax.errorbar(r.conversion_rate * 100, i, xerr=[[(r.conversion_rate - r.conversion_ci_low) * 100],
                        [(r.conversion_ci_high - r.conversion_rate) * 100]], fmt="o", color=cs.SERIES[0],
                        ms=7, elinewidth=1.5, capsize=0)
            ax.text(r.conversion_ci_high * 100 + 0.05, i, f"{r.conversion_rate:.2%}  (n={r.sessions:,})",
                    va="center", fontsize=8, color=cs.TEXT_2)
            labels.append(k)
            yy.append(i)
            i += 1
        i += 0.6
    ax.axvline(base["overall_conversion"] * 100, color=cs.TEXT_2, lw=1, ls="--")
    ax.set_yticks(yy, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Session conversion rate (%), 95% CI")
    ax.set_xlim(0, max(seg.conversion_ci_high) * 100 + 0.9)
    ax.grid(axis="y", visible=False)
    new = seg[(seg.segment_type == "user_type") & (seg.segment == "New")].iloc[0]
    ret = seg[(seg.segment_type == "user_type") & (seg.segment == "Returning")].iloc[0]
    cs.title(fig, f"Returning sessions convert {ret.conversion_rate / new.conversion_rate:.1f}x better than new ones "
                  f"({ret.conversion_rate:.2%} vs {new.conversion_rate:.2%});\n"
                  f"device makes almost no difference (dashed line = all sessions, {base['overall_conversion']:.2%})")
    cs.source_note(fig, "Groups top to bottom: device, new vs returning, first-touch medium. " + SOURCE)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(FIG / "m2_conversion_by_segment.png", dpi=160)


if __name__ == "__main__":
    main()
