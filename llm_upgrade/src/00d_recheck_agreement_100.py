"""Step 0d: Compare the person's blind labels with the AI-made labels on all 100 test reviews.

Script 00b did this for the first 30 reviews and is kept as it is. This script adds
the other 70 (worksheet from script 00c) and reports three groups:
- first30: labelled before the test run
- rest70:  labelled after the test results were published
- all100:  both together

Worksheet rules:
- `my_labels`: stage codes split by ; , or spaces. Blank, NONE or - means no stage.
- `notes` (optional): free text for unsure or edge cases. Not used for scoring.
  Notes are saved to a git-ignored file, because they may quote review text.

Inputs:  llm_upgrade/reports/test_recheck_labels.csv (the first 30, from script 00b)
         llm_upgrade/data/test_recheck_worksheet_rest70.csv (the other 70)
Outputs: reports/test_recheck_labels_100.csv (labels only, no review text)
         reports/label_recheck_agreement_100.json
         llm_upgrade/data/test_recheck_notes.csv (git-ignored: rows with notes only)
"""
import importlib
import json

import numpy as np
import pandas as pd

from common import CODE_LIST, DATA, REPORTS, labels_to_matrix, load_sample
from eval_metrics import cohen_kappa, per_stage

parse = importlib.import_module("00b_recheck_agreement").parse  # same parsing as the first 30

N_BOOT = 10000
SEED = 2026  # same seed as script 00b, so the first30 result can be checked against it
NO_STAGE = {"NONE", "-"}
SHEET = DATA / "test_recheck_worksheet_rest70.csv"
FIRST = REPORTS / "test_recheck_labels.csv"


def read_sheet(path):
    """Read UTF-8 first. Excel's plain "CSV" uses a Windows code page instead: GBK on
    Chinese Windows, or Windows-1252. Labels are ASCII codes, so they read the same in
    any of these. Review text is not used here."""
    for enc in ("utf-8-sig", "gbk", "cp1252"):
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
        if enc != "utf-8-sig":
            print(f"Warning: {path.name} is not UTF-8; read as {enc}. Check any notes look right.")
        return df
    raise SystemExit(f"Cannot read {path}. In Excel use Save As > 'CSV UTF-8'.")


def parse_labels(cell):
    return [c for c in parse(cell) if c not in NO_STAGE]


def check_sheet(sheet, expected_ids):
    """Parse the worksheet and stop with a clear message if anything is wrong."""
    for col in ("val_id", "my_labels"):
        if col not in sheet:
            raise SystemExit(f"Worksheet has no '{col}' column")
    sheet = sheet.copy()
    if "notes" not in sheet:
        sheet["notes"] = ""
    sheet["val_id"] = sheet["val_id"].astype(int)
    sheet["human"] = sheet["my_labels"].map(parse_labels)
    sheet["notes"] = sheet["notes"].fillna("").str.strip()
    bad = sorted({c for row in sheet["human"] for c in row} - set(CODE_LIST))
    problems = []
    if bad:
        problems.append(f"unknown codes {bad}")
    if sheet["val_id"].duplicated().any():
        problems.append("repeated val_id")
    if set(sheet["val_id"]) != set(expected_ids):
        problems.append("val_id values differ from the 70 expected reviews")
    if problems:
        raise SystemExit("Check the worksheet: " + "; ".join(problems))
    return sheet


def agreement(human_lists, ai_lists, n_boot=N_BOOT, seed=SEED):
    human, machine = labels_to_matrix(human_lists), labels_to_matrix(ai_lists)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        i = rng.integers(0, len(human), len(human))
        draws.append(cohen_kappa(human[i], machine[i]))
    lo, hi = np.nanpercentile(np.array(draws, dtype=float), [2.5, 97.5])
    return {
        "reviews": len(human), "cells": int(human.size),
        "kappa": cohen_kappa(human, machine), "kappa_ci95": [float(lo), float(hi)],
        "same_full_label_set": float((human == machine).all(axis=1).mean()),
        "reviews_with_no_stage": {"person": int((human.sum(1) == 0).sum()),
                                  "ai": int((machine.sum(1) == 0).sum())},
        "labels_given": {"person": int(human.sum()), "ai": int(machine.sum())},
        "per_stage_treating_person_as_truth": per_stage(human, machine, CODE_LIST),
    }


def combine(first, rest, ai):
    """One row per review, first 30 first (in script 00b's order), then the 70."""
    a = first[["val_id", "person_labels"]].copy()
    a["person"] = a["person_labels"].fillna("").map(parse_labels)
    a["label_round"] = "first30"
    b = rest[["val_id", "human"]].rename(columns={"human": "person"})
    b["label_round"] = "rest70"
    df = pd.concat([a[["val_id", "person", "label_round"]], b], ignore_index=True)
    return df.merge(ai, on="val_id", how="left", validate="one_to_one")


def main():
    ai = load_sample("test")[["val_id", "labels"]]
    first = pd.read_csv(FIRST, dtype={"person_labels": str})
    expected = sorted(set(ai["val_id"]) - set(first["val_id"]))
    rest = check_sheet(read_sheet(SHEET), expected)
    df = combine(first, rest, ai)
    if len(df) != 100 or df["labels"].isna().any():
        raise SystemExit("Expected 100 reviews that all match the test sample")

    out = {"note": "first30 were labelled before the test run; rest70 after the test "
                   "results were published. Notes are not used for scoring."}
    for name, part in (("all100", df), ("first30", df[df["label_round"] == "first30"]),
                       ("rest70", df[df["label_round"] == "rest70"])):
        out[name] = agreement(list(part["person"]), list(part["labels"]))
    out["reviews_with_notes"] = int((rest["notes"] != "").sum())

    (REPORTS / "label_recheck_agreement_100.json").write_text(json.dumps(out, indent=2),
                                                              encoding="utf-8")
    pd.DataFrame({"val_id": df["val_id"], "label_round": df["label_round"],
                  "person_labels": df["person"].map(";".join),
                  "ai_labels": df["labels"].map(";".join)}
                 ).to_csv(REPORTS / "test_recheck_labels_100.csv", index=False)
    notes = rest.loc[rest["notes"] != "", ["val_id", "my_labels", "notes"]]
    notes.to_csv(DATA / "test_recheck_notes.csv", index=False, encoding="utf-8-sig")

    for name in ("all100", "first30", "rest70"):
        s = out[name]
        print(f"{name}: n={s['reviews']} kappa={s['kappa']:.3f} "
              f"CI={[round(x, 3) for x in s['kappa_ci95']]} same_set={s['same_full_label_set']:.2f}")
    print(f"Notes kept for {len(notes)} reviews in {DATA / 'test_recheck_notes.csv'}")


if __name__ == "__main__":
    main()
