"""Step 0c: Make a blind re-labelling worksheet for the other 70 test reviews.

Script 00 made a worksheet for 30 random test reviews. This one makes the same
kind of worksheet for the 70 test reviews that were not in it, so a person can
label the whole test sample. The worksheet shows no AI labels, no rule tags and
no LLM tags. Rows are shuffled with a fixed seed, so the order gives no hint.

Note: these 70 are labelled after the test results were published. Report them
separately from the first 30, which were labelled before the test run.

Input:  data/processed/test_sample_blind.csv
        llm_upgrade/reports/test_recheck_labels.csv (the 30 already labelled)
Output: llm_upgrade/data/test_recheck_worksheet_rest70.csv (git-ignored: has review text)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "llm_upgrade" / "data" / "test_recheck_worksheet_rest70.csv"
DONE = ROOT / "llm_upgrade" / "reports" / "test_recheck_labels.csv"
SEED = 20261117
EXPECTED = 70


def make_sheet(test, done_ids, seed=SEED):
    """Return the test reviews not yet labelled, shuffled, with an empty label column."""
    rest = test[~test["val_id"].isin(set(done_ids))]
    sheet = rest.sample(frac=1, random_state=seed)[["val_id", "full_text"]].reset_index(drop=True)
    sheet["my_labels"] = ""
    return sheet


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} already exists. Delete it yourself to make a new one.")
    test = pd.read_csv(ROOT / "data/processed/test_sample_blind.csv")
    done = pd.read_csv(DONE)["val_id"]
    sheet = make_sheet(test, done)
    if len(sheet) != EXPECTED:
        raise SystemExit(f"Expected {EXPECTED} reviews, got {len(sheet)}. Check the inputs.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(OUT, index=False, encoding="utf-8-sig")  # utf-8-sig so Excel reads it correctly
    print(f"Saved {len(sheet)} reviews to {OUT}")


if __name__ == "__main__":
    main()
