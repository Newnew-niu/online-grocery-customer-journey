"""Step 5: What do the rules miss?

20% of negative reviews get no journey-stage tag. Here we look at them
with a simple topic model (LDA from scikit-learn) and word counts, to see
if there is a big theme the keyword rules do not cover.

Output: reports/untagged_negative_topics.txt
"""
from pathlib import Path

import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

ROOT = Path(__file__).resolve().parents[1]
EXTRA_STOP = ["app", "tesco", "dunnes", "supervalu", "stores", "store", "just", "use", "don", "t", "s",
              "ve", "im", "it's", "like", "get", "really", "even", "one", "would"]


def main():
    df = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    neg = df[df["rating_group"] == "negative"]
    untagged = neg[neg["n_stages"] == 0].copy()
    lines = [f"Untagged negative reviews: {len(untagged)} of {len(neg)}",
             f"Median length: {untagged['n_words'].median():.0f} words",
             f"Share with 5 words or fewer: {(untagged['n_words'] <= 5).mean():.1%}", ""]

    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    stop = list(ENGLISH_STOP_WORDS.union(EXTRA_STOP))
    vec = CountVectorizer(stop_words=stop, min_df=3, ngram_range=(1, 2))
    X = vec.fit_transform(untagged["full_text"].str.lower())
    words = vec.get_feature_names_out()

    counts = pd.Series(X.sum(axis=0).A1, index=words).sort_values(ascending=False)
    lines.append("Most common words: " + ", ".join(f"{w} ({c})" for w, c in counts.head(25).items()))
    lines.append("")

    lda = LatentDirichletAllocation(n_components=4, random_state=0)
    lda.fit(X)
    for k, comp in enumerate(lda.components_):
        top = [words[i] for i in comp.argsort()[::-1][:10]]
        lines.append(f"Topic {k + 1}: " + ", ".join(top))
    text = "\n".join(lines)
    (ROOT / "reports/untagged_negative_topics.txt").write_text(text, encoding="utf-8")
    print(text)
    # examples are printed only (not saved), so review text stays out of the repo
    print("\nRandom examples:")
    for t in untagged.sample(15, random_state=1)["full_text"]:
        print(" - " + t[:140].replace("\n", " "))


if __name__ == "__main__":
    main()
