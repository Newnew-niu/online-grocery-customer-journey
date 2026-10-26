"""Step 1: Collect app reviews for three Irish grocery apps.

Sources
- Google Play: the `google-play-scraper` library (country "ie", language "en").
- App Store: Apple's public customer-reviews RSS feed (country "ie").
  Apple only serves the 500 most recent reviews (10 pages x 50).

We keep reviews from the last 24 months only.
Output: data/raw/reviews/reviews_raw.csv
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from google_play_scraper import Sort, reviews

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "reviews" / "reviews_raw.csv"

# App IDs were checked by hand (publisher name + Irish store).
# Note: com.tesco.grocery.view is the UK Tesco app, so we do NOT use it.
APPS = {
    "Tesco": {"play": "com.puca.tesco", "ios": "648859363"},
    "Dunnes Stores": {"play": "com.dunnes.valueclubcard", "ios": "1539398657"},
    "SuperValu": {"play": "com.ammeon.supervalu", "ios": "538805121"},
}

RUN_DATE = datetime(2026, 10, 26, tzinfo=timezone.utc)  # date the data was collected
START_DATE = RUN_DATE - timedelta(days=730)  # last 24 months


def get_play_reviews(retailer, app_id, max_reviews=4000):
    rows = []
    token = None
    while len(rows) < max_reviews:
        batch, token = reviews(
            app_id, lang="en", country="ie", sort=Sort.NEWEST,
            count=200, continuation_token=token,
        )
        if not batch:
            break
        for r in batch:
            rows.append({
                "retailer": retailer,
                "store": "Google Play",
                "review_id": r["reviewId"],
                "date": r["at"],
                "rating": r["score"],
                "title": "",
                "text": r["content"],
                "app_version": r.get("reviewCreatedVersion"),
                "thumbs_up": r.get("thumbsUpCount"),
            })
        oldest = min(r["at"] for r in batch)
        if oldest < START_DATE.replace(tzinfo=None) or token is None:
            break
    return rows


def get_ios_reviews(retailer, app_id):
    rows = []
    for page in range(1, 11):
        url = (f"https://itunes.apple.com/ie/rss/customerreviews/"
               f"page={page}/id={app_id}/sortby=mostrecent/json")
        resp = requests.get(url, timeout=60)
        if resp.status_code != 200:
            break
        entries = resp.json().get("feed", {}).get("entry", [])
        if isinstance(entries, dict):
            entries = [entries]
        if not entries:
            break
        for e in entries:
            if "im:rating" not in e:  # first entry can be app info, not a review
                continue
            rows.append({
                "retailer": retailer,
                "store": "App Store",
                "review_id": e["id"]["label"],
                "date": pd.to_datetime(e["updated"]["label"]).tz_convert(None),
                "rating": int(e["im:rating"]["label"]),
                "title": e["title"]["label"],
                "text": e["content"]["label"],
                "app_version": e.get("im:version", {}).get("label"),
                "thumbs_up": int(e.get("im:voteSum", {}).get("label", 0)),
            })
    return rows


def main():
    all_rows = []
    for retailer, ids in APPS.items():
        play = get_play_reviews(retailer, ids["play"])
        ios = get_ios_reviews(retailer, ids["ios"])
        print(f"{retailer}: Google Play {len(play)}, App Store {len(ios)} (before date filter)")
        all_rows += play + ios

    df = pd.DataFrame(all_rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= START_DATE.replace(tzinfo=None)]
    df = df.drop_duplicates(subset=["store", "review_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print("\nSaved", len(df), "reviews from the last 24 months")
    print(df.groupby(["retailer", "store"]).size())
    print("Date range:", df["date"].min(), "to", df["date"].max())


if __name__ == "__main__":
    main()
