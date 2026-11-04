"""Step 0: Make a blind re-labelling worksheet for 30 test reviews.

The dev and test labels were made by an AI assistant in one pass. A person
re-labels a random 30 test reviews here, without seeing those labels or the
rule tags, so we can measure how far the AI labels can be trusted.

Input:  data/processed/test_sample_blind.csv
Output: llm_upgrade/data/test_recheck_worksheet.csv (git-ignored: has review text)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "llm_upgrade" / "data" / "test_recheck_worksheet.csv"
N = 30
SEED = 20261104


def main():
    if OUT.exists():
        raise SystemExit(f"{OUT} already exists. Delete it yourself to make a new one.")
    test = pd.read_csv(ROOT / "data/processed/test_sample_blind.csv")
    sheet = test.sample(N, random_state=SEED)[["val_id", "full_text"]]
    sheet.insert(2, "my_labels", "")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.to_csv(OUT, index=False, encoding="utf-8-sig")  # utf-8-sig so Excel reads it correctly
    print(f"Saved {len(sheet)} reviews to {OUT}")


if __name__ == "__main__":
    main()
