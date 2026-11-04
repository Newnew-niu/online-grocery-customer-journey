"""Shared paths, stage codes and sample loading for the LLM upgrade."""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
UPGRADE = ROOT / "llm_upgrade"
DATA = UPGRADE / "data"
REPORTS = UPGRADE / "reports"
PROMPTS = UPGRADE / "prompts"

# Reuse the original code, so the comparison is like for like.
sys.path.insert(0, str(ROOT / "src"))
CODES = importlib.import_module("03_validate_tags").CODES
CODE_LIST = list(CODES)


def labels_to_row(labels):
    """Turn a list of codes into a 0/1 row in CODE_LIST order."""
    return [int(c in labels) for c in CODE_LIST]


def labels_to_matrix(label_lists):
    return np.array([labels_to_row(x) for x in label_lists], dtype=int).reshape(-1, len(CODE_LIST))


def load_sample(name):
    """Load a check sample with its label codes as a list in `labels`."""
    sample = pd.read_csv(ROOT / f"data/processed/{name}_sample_blind.csv")
    manual = pd.read_csv(ROOT / f"data/processed/{name}_labels_manual.csv").fillna("")
    df = sample.merge(manual, on="val_id")
    df["labels"] = df["manual_labels"].map(lambda x: [c for c in x.split(";") if c])
    return df
