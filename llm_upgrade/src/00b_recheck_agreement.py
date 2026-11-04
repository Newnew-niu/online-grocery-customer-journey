"""Step 0b: Compare the person's blind labels with the AI-made labels.

Run this before the test run. It shows how far the AI labels can be trusted.
Kappa is over all review-stage cells (30 reviews x 10 stages), with a bootstrap
95% CI over reviews, because 30 reviews is a small sample.

Input:  llm_upgrade/data/test_recheck_worksheet.csv
Output: reports/test_recheck_labels.csv (labels only, no review text)
        reports/label_recheck_agreement.json
"""
import json
import re

import numpy as np
import pandas as pd

from common import CODE_LIST, DATA, REPORTS, labels_to_matrix, load_sample
from eval_metrics import cohen_kappa, per_stage

N_BOOT = 10000
SEED = 2026


def read_sheet():
    path = DATA / "test_recheck_worksheet.csv"
    try:
        return pd.read_csv(path, encoding="utf-8-sig", dtype=str).fillna("")
    except UnicodeDecodeError:  # Excel may save a plain "CSV" in a Chinese Windows code page. Review text is not used here.
        return pd.read_csv(path, encoding="gbk", encoding_errors="replace", dtype=str).fillna("")


def parse(cell):
    return [c for c in re.split(r"[;；,，\s]+", cell.strip().upper()) if c]


def main():
    sheet = read_sheet()
    sheet["val_id"] = sheet["val_id"].astype(int)
    sheet["human"] = sheet["my_labels"].map(parse)
    bad = sorted({c for row in sheet["human"] for c in row} - set(CODE_LIST))
    if bad or len(sheet) != 30 or sheet["val_id"].duplicated().any():
        raise SystemExit(f"Check the worksheet: rows={len(sheet)}, unknown codes={bad}")

    ai = load_sample("test")[["val_id", "labels"]]
    df = sheet.merge(ai, on="val_id", validate="one_to_one")
    if len(df) != 30:
        raise SystemExit("Some val_id values do not match the test sample")
    human, machine = labels_to_matrix(df["human"]), labels_to_matrix(df["labels"])

    rng = np.random.default_rng(SEED)
    draws = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(df), len(df))
        draws.append(cohen_kappa(human[i], machine[i]))
    lo, hi = np.nanpercentile(np.array(draws, dtype=float), [2.5, 97.5])

    out = {
        "reviews": len(df), "cells": int(human.size),
        "kappa": cohen_kappa(human, machine), "kappa_ci95": [float(lo), float(hi)],
        "same_full_label_set": float((human == machine).all(axis=1).mean()),
        "reviews_with_no_stage": {"person": int((human.sum(1) == 0).sum()),
                                  "ai": int((machine.sum(1) == 0).sum())},
        "labels_given": {"person": int(human.sum()), "ai": int(machine.sum())},
        "per_stage_treating_person_as_truth": per_stage(human, machine, CODE_LIST),
    }
    (REPORTS / "label_recheck_agreement.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    pd.DataFrame({"val_id": df["val_id"], "person_labels": df["human"].map(";".join),
                  "ai_labels": df["labels"].map(";".join)}
                 ).to_csv(REPORTS / "test_recheck_labels.csv", index=False)
    print({k: v for k, v in out.items() if k != "per_stage_treating_person_as_truth"})
    print(pd.DataFrame(out["per_stage_treating_person_as_truth"]).T[["tp", "fp", "fn"]].to_string())


if __name__ == "__main__":
    main()
