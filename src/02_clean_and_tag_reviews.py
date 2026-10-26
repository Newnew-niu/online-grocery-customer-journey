"""Step 2: Clean reviews, keep English, add sentiment and journey-stage tags.

Input:  data/raw/reviews/reviews_raw.csv
Output: data/processed/reviews_tagged.csv
"""
from pathlib import Path

import pandas as pd
from langdetect import DetectorFactory, detect_langs
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from journey_rules import STAGES, tag_text

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "reviews" / "reviews_raw.csv"
OUT = ROOT / "data" / "processed" / "reviews_tagged.csv"

DetectorFactory.seed = 0  # make language detection repeatable


COMMON_EN = {"the", "and", "is", "it", "to", "in", "app", "not", "my", "of", "i",
             "you", "a", "on", "for", "use", "this", "doesn't", "same", "are"}


def is_english(text):
    """Language detection is not reliable for very short texts like 'very good'.
    So we only drop a review when it has 5+ words, has no very
    common English words, AND the detector is at least 90% sure it is not English."""
    words = text.lower().split()
    if len(words) < 5 or len(COMMON_EN & set(words)) >= 1:
        return True
    try:
        top = detect_langs(text)[0]
    except Exception:
        return True
    return not (top.lang != "en" and top.prob >= 0.90)


def main():
    df = pd.read_csv(RAW, parse_dates=["date"])
    n_start = len(df)

    df["title"] = df["title"].fillna("")
    df["text"] = df["text"].fillna("").str.strip()
    df = df[df["text"].str.len() > 0]
    df["full_text"] = (df["title"] + ". " + df["text"]).str.strip(". ")
    n_nonempty = len(df)

    df["is_english"] = df["full_text"].map(is_english)
    dropped = df[~df["is_english"]]
    df = df[df["is_english"]].drop(columns="is_english")

    df["n_words"] = df["text"].str.split().str.len()

    # Sentiment: star rating + VADER compound score (-1 very negative, +1 very positive)
    analyzer = SentimentIntensityAnalyzer()
    df["vader"] = df["full_text"].map(lambda t: analyzer.polarity_scores(t)["compound"])
    df["rating_group"] = pd.cut(df["rating"], [0, 2, 3, 5], labels=["negative", "neutral", "positive"])

    tags = pd.DataFrame([tag_text(t) for t in df["full_text"]], index=df.index)
    df = pd.concat([df, tags], axis=1)
    df["n_stages"] = df[list(STAGES)].sum(axis=1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    print(f"Raw reviews: {n_start}")
    print(f"After removing empty text: {n_nonempty}")
    print(f"Dropped as non-English: {len(dropped)}")
    if len(dropped):
        print(dropped["full_text"].str[:80].to_string())
    print(f"Final reviews: {len(df)}")
    print(df.groupby("retailer").size())
    print("\nRating groups:\n", df.groupby(["retailer", "rating_group"], observed=True).size().unstack())
    print("\nShare of reviews with at least one stage tag:", round((df["n_stages"] > 0).mean(), 3))
    neg = df[df["rating_group"] == "negative"]
    print("Share of NEGATIVE reviews with at least one stage tag:", round((neg["n_stages"] > 0).mean(), 3))
    print("Correlation between rating and VADER score:", round(df["rating"].corr(df["vader"]), 3))


if __name__ == "__main__":
    main()
