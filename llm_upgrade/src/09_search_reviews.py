"""Step 9: Search reviews by meaning.

Example (run from llm_upgrade/src):
  python 09_search_reviews.py "login keeps failing" --retailer tesco --k 5
"""
import argparse

import chromadb
from sentence_transformers import SentenceTransformer

from common import DATA

COLLECTION = "reviews"
RETAILERS = ["tesco", "dunnes", "supervalu"]


def open_index():
    client = chromadb.PersistentClient(path=str(DATA / "chroma"))
    col = client.get_collection(COLLECTION)
    return col, SentenceTransformer(col.metadata["embed_model"])


def search(col, model, query, k=5, where=None):
    vector = model.encode([query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=vector, n_results=k, where=where)
    return [{"id": i, "score": 1 - d, "text": t, **m} for i, d, t, m in
            zip(res["ids"][0], res["distances"][0], res["documents"][0], res["metadatas"][0])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--retailer", choices=RETAILERS)
    ap.add_argument("--k", type=int, default=5)
    args = ap.parse_args()

    col, model = open_index()
    where = {"retailer_key": args.retailer} if args.retailer else None
    for r in search(col, model, args.query, args.k, where):
        print(f"[{r['score']:.3f}] {r['retailer']} | {r['store']} | {r['rating']} stars | "
              f"{r['date']} | stages: {r['llm_stages'] or '-'}")
        print("   " + r["text"][:200].replace("\n", " "))


if __name__ == "__main__":
    main()
