"""Step 9b: Evaluate semantic search against a keyword baseline (BM25).

Queries come from reports/retrieval_queries.json, written before any results were seen.
Only labelled reviews can be judged, so both methods search the 200 dev + test reviews.
A result is relevant if its AI-made label has the query's stage.

Rare stages have few relevant reviews, so even a perfect search cannot reach 1.0.
The `ceiling` columns show the best possible score.

Outputs: reports/retrieval_eval.csv, reports/retrieval_metrics.json
"""
import importlib
import json
import re

import pandas as pd
from rank_bm25 import BM25Okapi

from common import CODE_LIST, REPORTS, load_sample

open_index = importlib.import_module("09_search_reviews").open_index
search = importlib.import_module("09_search_reviews").search

KS = (5, 10)


def tokens(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def main():
    queries = json.loads((REPORTS / "retrieval_queries.json").read_text(encoding="utf-8"))["queries"]
    df = pd.concat([load_sample("dev"), load_sample("test")], ignore_index=True)
    relevant = {c: set(df.loc[df["labels"].map(lambda x: c in x), "review_id"]) for c in CODE_LIST}
    ids = df["review_id"].tolist()
    bm25 = BM25Okapi([tokens(t) for t in df["full_text"]])
    col, model = open_index()
    labelled = {"sample": {"$in": ["dev", "test"]}}

    rows = []
    for code in CODE_LIST:
        scores = bm25.get_scores(tokens(queries[code]))
        keyword = [ids[i] for i in sorted(range(len(ids)), key=lambda i: -scores[i])[:max(KS)]]
        semantic = [r["id"] for r in search(col, model, queries[code], max(KS), labelled)]
        row = {"stage": code, "query": queries[code], "relevant_reviews": len(relevant[code])}
        for k in KS:
            row[f"semantic_p{k}"] = len(set(semantic[:k]) & relevant[code]) / k
            row[f"bm25_p{k}"] = len(set(keyword[:k]) & relevant[code]) / k
            row[f"ceiling_p{k}"] = min(len(relevant[code]), k) / k
        rows.append(row)
    res = pd.DataFrame(rows)
    res.to_csv(REPORTS / "retrieval_eval.csv", index=False)

    summary = {"queries": len(res), "corpus": len(df), "relevance": "AI-made labels",
               "embed_model": col.metadata["embed_model"]}
    for k in KS:
        s, b = res[f"semantic_p{k}"], res[f"bm25_p{k}"]
        summary[f"p{k}"] = {"semantic": float(s.mean()), "bm25": float(b.mean()),
                            "ceiling": float(res[f"ceiling_p{k}"].mean()),
                            "semantic_wins": int((s > b).sum()), "ties": int((s == b).sum()),
                            "bm25_wins": int((b > s).sum())}
    (REPORTS / "retrieval_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(res.drop(columns="query").round(2).to_string(index=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
