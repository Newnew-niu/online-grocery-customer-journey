"""Step 13: How much do the scores change when the reference labels change?

Scores both vendors (keyword rules, LLM) against two reference label sets on the SAME
reviews, so each comparison is paired:
- ai:     the AI-made labels (the original reference)
- person: the person's blind labels
Groups: all 100 test reviews, the first 30 (labelled before the LLM test run) and the
other 70 (labelled after its results were published).

The earlier comparison (Module 5 report) was not paired: AI labels on 100 reviews vs the
person's labels on 30. This one uses the same reviews for both references.

Inputs (git-ignored ones are marked *):
  reports/test_recheck_labels_100.csv, data/llm_tags_test_journey_stage_v2.csv*,
  ../data/processed/test_sample_blind.csv*
Output: reports/label_source_effect.csv
No API calls.
"""
import pandas as pd

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, labels_to_matrix
from eval_metrics import micro, stage_counts

from journey_rules import tag_text  # noqa: E402  (original src/, put on the path by common)

GROUPS = ["all100", "first30", "rest70"]
REFERENCES = ["ai", "person"]
VENDORS = ["rules", "llm"]


def codes(cell):
    return [c for c in str(cell).split(";") if c and c != "nan"]


def score_table(df):
    """df columns: label_round, ai, person, rules, llm (each a list of codes)."""
    rows = []
    for g in GROUPS:
        part = df if g == "all100" else df[df["label_round"] == g]
        for v in VENDORS:
            pred = labels_to_matrix(list(part[v]))
            out = {"group": g, "reviews": len(part), "vendor": v}
            for ref in REFERENCES:
                truth = labels_to_matrix(list(part[ref]))
                tp, fp, fn = (int(x.sum()) for x in stage_counts(truth, pred))
                s = micro(truth, pred)
                out.update({f"{ref}_tp": tp, f"{ref}_fp": fp, f"{ref}_fn": fn,
                            f"{ref}_precision": s["precision"], f"{ref}_recall": s["recall"], f"{ref}_f1": s["f1"]})
            for m in ("precision", "recall", "f1"):
                out[f"{m}_change_person_minus_ai"] = out[f"person_{m}"] - out[f"ai_{m}"]
            rows.append(out)
    return pd.DataFrame(rows)


def main():
    labels = pd.read_csv(REPORTS / "test_recheck_labels_100.csv", dtype=str, keep_default_na=False)
    labels["val_id"] = labels["val_id"].astype(int)
    test = pd.read_csv(ROOT / "data/processed/test_sample_blind.csv")[["val_id", "full_text"]]
    tags = pd.read_csv(DATA / "llm_tags_test_journey_stage_v2.csv", keep_default_na=False)[["val_id", "llm_labels"]]
    df = labels.merge(test, on="val_id", validate="one_to_one").merge(tags, on="val_id", validate="one_to_one")
    df["ai"] = df["ai_labels"].map(codes)
    df["person"] = df["person_labels"].map(codes)
    df["llm"] = df["llm_labels"].map(codes)
    df["rules"] = [[c for c in CODE_LIST if tag_text(t)[CODES[c]]] for t in df["full_text"]]
    out = score_table(df)
    out.to_csv(REPORTS / "label_source_effect.csv", index=False)
    show = ["group", "vendor", "ai_precision", "person_precision", "ai_recall", "person_recall", "ai_f1", "person_f1"]
    print(out[show].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
