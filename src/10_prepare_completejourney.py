"""Step 10: Prepare The Complete Journey data (84.51° release).

Data: an anonymised US grocery retailer, 2,469 households, calendar year 2017.
It is NOT Tesco data.

What we do
- Read the R data files with pyreadr.
- Remove non-grocery lines: FUEL and MISCELLANEOUS departments. Their
  "quantity" is not a count of items (fuel lines have quantities up to 89,638),
  and fuel spend would distort grocery basket values.
- Build a basket-level table (one row per shopping trip).

Outputs (data/processed/):
- cj_lines.parquet   : cleaned transaction lines
- cj_baskets.parquet : one row per basket
"""
from pathlib import Path

import pandas as pd
import pyreadr

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "completejourney"
OUT = ROOT / "data" / "processed"
EXCLUDE_DEPTS = ["FUEL", "MISCELLANEOUS"]


def read(name):
    path = RAW / name
    res = pyreadr.read_r(path)
    return next(iter(res.values()))


def main():
    t = read("transactions.rds")
    p = read("products.rda")
    n0 = len(t)

    t = t.merge(p[["product_id", "department", "brand"]], on="product_id", how="left")
    t = t[~t["department"].isin(EXCLUDE_DEPTS)]
    n1 = len(t)
    t = t[t["quantity"] > 0]  # lines with 0 quantity are returns/adjustments
    n2 = len(t)
    t["used_coupon"] = (t["coupon_disc"] > 0).astype(int)
    t["date"] = t["transaction_timestamp"].dt.normalize()
    t.to_parquet(OUT / "cj_lines.parquet", index=False)

    b = t.groupby(["household_id", "basket_id"], observed=True).agg(
        date=("date", "min"),
        week=("week", "min"),
        store_id=("store_id", "first"),
        spend=("sales_value", "sum"),
        items=("quantity", "sum"),
        lines=("product_id", "size"),
        retail_disc=("retail_disc", "sum"),
        coupon_disc=("coupon_disc", "sum"),
        used_coupon=("used_coupon", "max"),
    ).reset_index()
    b.to_parquet(OUT / "cj_baskets.parquet", index=False)

    print(f"Transaction lines: {n0:,}")
    print(f"After removing FUEL and MISCELLANEOUS: {n1:,} ({n0 - n1:,} removed)")
    print(f"After removing zero-quantity lines: {n2:,}")
    print(f"Households: {b.household_id.nunique():,}  Baskets: {len(b):,}")
    print(f"Date range: {b.date.min().date()} to {b.date.max().date()}")


if __name__ == "__main__":
    main()
