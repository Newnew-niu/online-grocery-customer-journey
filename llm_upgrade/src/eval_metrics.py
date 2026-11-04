"""Precision, recall and F1 with the same counts as src/03_validate_tags.py.

Inputs are 0/1 matrices: one row per review, one column per stage.
A metric with an empty denominator is None (not 0), as in script 03.
Macro averages skip stages where the metric is None.
"""
import numpy as np


def _safe(top, bottom):
    return top / bottom if bottom else None


def prf(tp, fp, fn):
    p = _safe(tp, tp + fp)
    r = _safe(tp, tp + fn)
    f1 = None if tp + fp + fn == 0 else 2 * tp / (2 * tp + fp + fn)
    return {"precision": p, "recall": r, "f1": f1}


def stage_counts(truth, pred):
    tp = ((pred == 1) & (truth == 1)).sum(axis=0)
    fp = ((pred == 1) & (truth == 0)).sum(axis=0)
    fn = ((pred == 0) & (truth == 1)).sum(axis=0)
    return tp, fp, fn


def per_stage(truth, pred, codes):
    tp, fp, fn = stage_counts(truth, pred)
    return {c: {"tp": int(a), "fp": int(b), "fn": int(d), **prf(int(a), int(b), int(d))}
            for c, a, b, d in zip(codes, tp, fp, fn)}


def micro(truth, pred):
    tp, fp, fn = stage_counts(truth, pred)
    return prf(int(tp.sum()), int(fp.sum()), int(fn.sum()))


def macro(truth, pred):
    tp, fp, fn = stage_counts(truth, pred)
    rows = [prf(int(a), int(b), int(d)) for a, b, d in zip(tp, fp, fn)]
    out = {}
    for m in ("precision", "recall", "f1"):
        vals = [r[m] for r in rows if r[m] is not None]
        out[m] = float(np.mean(vals)) if vals else None
    return out


def bootstrap_ci(truth, preds, n_boot=10000, seed=2026):
    """95% CIs by resampling reviews. The same resamples are used for every
    method, so the differences against the first method are paired.

    preds: dict {name: matrix}. The first name is the reference.
    """
    rng = np.random.default_rng(seed)
    n = len(truth)
    names = list(preds)
    draws = {nm: {m: [] for m in ("precision", "recall", "f1")} for nm in names}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        for nm in names:
            s = micro(truth[idx], preds[nm][idx])
            for m in draws[nm]:
                draws[nm][m].append(np.nan if s[m] is None else s[m])

    def ci(values):
        lo, hi = np.nanpercentile(values, [2.5, 97.5])
        return [float(lo), float(hi)]

    base = names[0]
    out = {}
    for nm in names:
        out[nm] = {m: ci(v) for m, v in draws[nm].items()}
        if nm != base:
            d = {m: np.array(draws[nm][m]) - np.array(draws[base][m]) for m in draws[nm]}
            out[nm]["diff_vs_" + base] = {m: ci(v) for m, v in d.items()}
    return out


def cohen_kappa(a, b):
    """Agreement between two 0/1 matrices, over all review-stage cells."""
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    observed = (a == b).mean()
    pa, pb = a.mean(), b.mean()
    expected = pa * pb + (1 - pa) * (1 - pb)
    return None if expected == 1 else float((observed - expected) / (1 - expected))
