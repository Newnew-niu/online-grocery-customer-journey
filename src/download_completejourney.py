"""Download "The Complete Journey" data files.

Source: the open `completejourney` R package by Brad Boehmke
(https://github.com/bradleyboehmke/completejourney).
The data was released by 84.51° (a retail data science company).
It is from an anonymised US grocery retailer. It is NOT Tesco data.

Files are saved to data/raw/completejourney/.
"""
from pathlib import Path

import requests

BASE_URL = "https://github.com/bradleyboehmke/completejourney/raw/master/data/"
FILES = [
    "campaign_descriptions.rda",
    "campaigns.rda",
    "coupon_redemptions.rda",
    "coupons.rda",
    "demographics.rda",
    "products.rda",
    "promotions_sample.rda",
    "transactions.rds",  # full transactions (about 1.47 million rows)
]

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "completejourney"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        path = OUT_DIR / name
        if path.exists():
            print("already have", name)
            continue
        print("downloading", name)
        resp = requests.get(BASE_URL + name, timeout=120)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    print("done")


if __name__ == "__main__":
    main()
