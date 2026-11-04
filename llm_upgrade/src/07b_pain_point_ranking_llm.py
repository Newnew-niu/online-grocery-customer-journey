"""Step 7b: Rebuild the Module 1 pain-point ranking with the LLM tags.

Same measures as src/04_pain_point_ranking.py, on the same 2,091 reviews.
The two methods answer slightly different questions: the rules find any mention
of a stage, while the LLM prompt tags problems only. On reviews with 1-2 stars this
matters little. On praise it matters a lot, so `avg_rating_when_mentioned` is not
like for like.

Outputs:
- reports/pain_point_ranking_llm.csv
- reports/pain_point_ranking_compare.csv
"""
import json

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, labels_to_row
from journey_rules import STAGE_LABELS

RETAILERS = ["Tesco", "Dunnes Stores", "SuperValu"]


def main():
    prompt = json.loads((REPORTS / "frozen_prompt.json").read_text(encoding="utf-8"))["frozen_prompt"]
    df = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    tags = pd.read_csv(DATA / f"llm_tags_all_{prompt}.csv").fillna("")
    df = df.merge(tags[["review_id", "ok", "llm_labels"]], on="review_id", validate="one_to_one")
    if not df["ok"].all():
        print(f"LLM failures counted as no stage: {(~df['ok']).sum()}")
    flags = pd.DataFrame([labels_to_row(x.split(";")) for x in df["llm_labels"]],
                         columns=[CODES[c] for c in CODE_LIST], index=df.index)
    df[flags.columns] = flags  # replaces the rule tags with the LLM tags
    neg = df[df["rating_group"] == "negative"]

    rows = []
    for r in RETAILERS + ["All three"]:
        sub = neg if r == "All three" else neg[neg["retailer"] == r]
        allr = df if r == "All three" else df[df["retailer"] == r]
        for s in flags.columns:
            k, n = int(sub[s].sum()), len(sub)
            lo, hi = proportion_confint(k, n, method="wilson")
            rows.append({
                "retailer": r, "stage": STAGE_LABELS[s], "negative_reviews": n,
                "negative_mentioning": k, "share_of_negative": round(k / n, 3),
                "ci_low": round(lo, 3), "ci_high": round(hi, 3),
                "avg_rating_when_mentioned": round(allr.loc[allr[s] == 1, "rating"].mean(), 2),
                "reviews_mentioning_any_rating": int(allr[s].sum()),
            })
    rank = pd.DataFrame(rows)
    rank["rank_in_retailer"] = (rank.groupby("retailer")["share_of_negative"]
                                .rank(ascending=False, method="min").astype(int))
    rank = rank.sort_values(["retailer", "rank_in_retailer"])
    rank.to_csv(REPORTS / "pain_point_ranking_llm.csv", index=False)

    old = pd.read_csv(ROOT / "reports/pain_point_ranking.csv")
    cols = ["retailer", "stage", "share_of_negative", "rank_in_retailer"]
    both = old[cols].merge(rank[cols], on=["retailer", "stage"], suffixes=("_rules", "_llm"))
    both["share_change"] = (both["share_of_negative_llm"] - both["share_of_negative_rules"]).round(3)
    both.sort_values(["retailer", "rank_in_retailer_llm"]).to_csv(
        REPORTS / "pain_point_ranking_compare.csv", index=False)
    print(both[both.retailer == "All three"].sort_values("rank_in_retailer_llm").to_string(index=False))
    corr = both.groupby("retailer")[["rank_in_retailer_rules", "rank_in_retailer_llm"]].corr(
        method="spearman").iloc[0::2, 1]
    print("Spearman rank correlation by retailer:\n", corr.round(2).to_string())


if __name__ == "__main__":
    main()
