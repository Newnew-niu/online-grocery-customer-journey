"""Step 8: Embed all reviews and store them in a persistent vector store (ChromaDB).

Uses a free local model. No review text leaves this computer in this step.

Input:  data/processed/reviews_tagged.csv, the LLM tags from step 6
Output: llm_upgrade/data/chroma/ (git-ignored)
"""
import json

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer

from common import CODE_LIST, CODES, DATA, REPORTS, ROOT, load_sample

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION = "reviews"
BATCH = 1000


def rule_stages(row):
    return ";".join(c for c in CODE_LIST if row[CODES[c]] == 1)


def main():
    prompt = json.loads((REPORTS / "frozen_prompt.json").read_text(encoding="utf-8"))["frozen_prompt"]
    df = pd.read_csv(ROOT / "data/processed/reviews_tagged.csv")
    tags = pd.read_csv(DATA / f"llm_tags_all_{prompt}.csv").fillna("")
    df = df.merge(tags[["review_id", "llm_labels"]], on="review_id", validate="one_to_one")
    sample = {r: name for name in ("dev", "test") for r in load_sample(name)["review_id"]}

    model = SentenceTransformer(EMBED_MODEL)
    vectors = model.encode(df["full_text"].tolist(), batch_size=64, normalize_embeddings=True,
                           show_progress_bar=False).tolist()
    meta = [{
        "retailer": r["retailer"], "retailer_key": r["retailer"].lower().split()[0],
        "store": r["store"], "rating": int(r["rating"]), "date": str(r["date"])[:10],
        "rule_stages": rule_stages(r), "llm_stages": r["llm_labels"],
        "sample": sample.get(r["review_id"], "none"),
    } for _, r in df.iterrows()]

    client = chromadb.PersistentClient(path=str(DATA / "chroma"))
    if COLLECTION in [c.name for c in client.list_collections()]:
        client.delete_collection(COLLECTION)
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine", "embed_model": EMBED_MODEL})
    ids, docs = df["review_id"].astype(str).tolist(), df["full_text"].tolist()
    for i in range(0, len(ids), BATCH):
        col.add(ids=ids[i:i + BATCH], documents=docs[i:i + BATCH],
                embeddings=vectors[i:i + BATCH], metadatas=meta[i:i + BATCH])
    print(f"Indexed {col.count()} reviews with {EMBED_MODEL}")


if __name__ == "__main__":
    main()
