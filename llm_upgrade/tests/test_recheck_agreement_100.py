"""Tests for script 00d. Synthetic data only: no network and no real reviews."""
import importlib

import pandas as pd
import pytest

m = importlib.import_module("00d_recheck_agreement_100")


def sheet(rows, notes=True):
    df = pd.DataFrame(rows, columns=["val_id", "my_labels", "notes"])
    df.insert(1, "full_text", "text")
    df = df.astype(str)
    return df if notes else df.drop(columns="notes")


def test_notes_column_is_optional():
    s = m.check_sheet(sheet([[1, "AP", "x"], [2, "", ""]], notes=False), [1, 2])
    assert list(s["notes"]) == ["", ""]
    assert list(s["human"]) == [["AP"], []]


def test_notes_are_kept_and_not_scored():
    s = m.check_sheet(sheet([[1, "AP;PL", " unsure: AP or CP? "], [2, "NONE", ""]]), [1, 2])
    assert list(s["human"]) == [["AP", "PL"], []]
    assert s.loc[0, "notes"] == "unsure: AP or CP?"


@pytest.mark.parametrize("cell,expected", [
    ("", []), ("NONE", []), ("-", []), ("ap, pl", ["AP", "PL"]), ("AL；SB", ["AL", "SB"]),
])
def test_label_parsing(cell, expected):
    assert m.parse_labels(cell) == expected


@pytest.mark.parametrize("rows,ids", [
    ([[1, "XX", ""], [2, "", ""]], [1, 2]),      # unknown code
    ([[1, "AP", ""], [1, "", ""]], [1, 2]),      # repeated id
    ([[1, "AP", ""], [3, "", ""]], [1, 2]),      # wrong ids
])
def test_bad_sheets_stop(rows, ids):
    with pytest.raises(SystemExit):
        m.check_sheet(sheet(rows), ids)


def test_missing_label_column_stops():
    with pytest.raises(SystemExit):
        m.check_sheet(pd.DataFrame({"val_id": ["1"]}), [1])


def test_agreement_perfect_and_counts():
    labels = [["AP"], [], ["PL", "AL"]]
    out = m.agreement(labels, labels, n_boot=20)
    assert out["kappa"] == 1.0
    assert out["same_full_label_set"] == 1.0
    assert out["labels_given"] == {"person": 3, "ai": 3}
    assert out["reviews_with_no_stage"] == {"person": 1, "ai": 1}


def test_combine_keeps_first30_order_then_rest():
    first = pd.DataFrame({"val_id": [5, 2], "person_labels": ["AP", None]})
    rest = pd.DataFrame({"val_id": [9], "human": [["PL"]]})
    ai = pd.DataFrame({"val_id": [2, 5, 9], "labels": [[], ["AP"], ["PL"]]})
    df = m.combine(first, rest, ai)
    assert list(df["val_id"]) == [5, 2, 9]
    assert list(df["label_round"]) == ["first30", "first30", "rest70"]
    assert list(df["person"]) == [["AP"], [], ["PL"]]
