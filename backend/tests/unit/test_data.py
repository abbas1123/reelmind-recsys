"""Preprocessing building blocks: title parsing, validation, splitting, safe extraction."""

from __future__ import annotations

import zipfile

import numpy as np
import pandas as pd
import pytest

from recsys.config import ValidationConfig
from recsys.data.download import _safe_extract
from recsys.data.features import display_title, genre_matrix, same_title, split_title_year
from recsys.data.split import check_leakage, global_temporal_split, per_user_temporal_split
from recsys.data.validate import validate_interactions


@pytest.mark.parametrize(
    ("raw", "title", "year"),
    [
        ("Toy Story (1995)", "Toy Story", 1995),
        ("Matrix, The (1999)", "The Matrix", 1999),
        ("Postman, The (Postino, Il) (1994)", "The Postman (Il Postino)", 1994),
        ("Misérables, Les (1995)", "Les Misérables", 1995),
        ("Untitled", "Untitled", None),
    ],
)
def test_title_parsing(raw, title, year):
    t, y = split_title_year(raw)
    assert y == year
    assert display_title(t) == title


def test_same_title_tolerates_alt_titles_and_subtitles():
    assert same_title("Postino, Il (The Postman) (1994)", "Postman, The (Postino, Il) (1994)")
    assert same_title("Interview with the Vampire (1994)", "Interview with the Vampire: The Vampire Chronicles (1994)")
    assert same_title("Dolores Claiborne (1994)", "Dolores Claiborne (1995)")
    assert not same_title("Heat (1995)", "Heat (1972)")
    assert not same_title("Alien (1979)", "Aliens (1986)")


def test_genre_matrix_multi_hot():
    m = genre_matrix(pd.Series([["Comedy", "Drama"], [], ["Drama"]]), ["Comedy", "Drama"])
    assert m.toarray().tolist() == [[1, 1], [0, 0], [0, 1]]


def test_validation_counts_every_rule():
    cfg = ValidationConfig(rating_min=1, rating_max=5, ts_min="2000-01-01", ts_max="2001-01-01")
    ok_ts = int(pd.Timestamp("2000-06-01", tz="UTC").timestamp())
    df = pd.DataFrame({
        "user_id": pd.array([1, 1, 2, 3, 4, 5, 1, None], dtype="Int64"),
        "item_id": pd.array([10, 10, 10, 99, 10, 10, 11, 10], dtype="Int64"),
        "rating": pd.array([4, 5, 7, 3, 3.5, 2, 1, 3], dtype="Float32"),
        "ts": pd.array([ok_ts, ok_ts + 5, ok_ts, ok_ts, ok_ts, 10, ok_ts, ok_ts], dtype="Int64"),
    })
    clean, report = validate_interactions(df, pd.Series([10, 11]), pd.Series([1, 2, 3, 4, 5]), cfg)
    r = report["rules"]
    assert r["missing_values"] == 1
    assert r["non_integer_rating"] == 1          # 3.5
    assert r["rating_out_of_range"] == 1         # 7
    assert r["timestamp_out_of_range"] == 1      # ts=10
    assert r["unknown_item"] == 1                # 99
    assert r["duplicate_user_item"] == 1         # user 1 rated item 10 twice
    assert len(clean) == 2
    # the most recent duplicate wins
    assert clean.loc[(clean.user_id == 1) & (clean.item_id == 10), "rating"].item() == 5


def test_global_temporal_split_has_no_time_overlap(toy_interactions):
    df = toy_interactions
    labels = global_temporal_split(df, 0.2, 0.2)
    df = df.assign(split=labels)
    checks = check_leakage(df, "split", "global_temporal")
    assert checks["temporal_order_ok"]
    assert set(labels) == {"train", "val", "test"}


def test_global_split_keeps_equal_timestamps_together():
    df = pd.DataFrame({"user_id": np.arange(10), "item_id": np.arange(10), "rating": 4.0,
                       "ts": [1, 1, 1, 1, 1, 1, 1, 1, 2, 2]})
    labels = global_temporal_split(df, 0.1, 0.1)
    assert labels[df.ts == 1].nunique() == 1


def test_per_user_split_holds_out_latest(toy_interactions):
    labels = per_user_temporal_split(toy_interactions, 0.34, 0.34)
    df = toy_interactions.assign(split=labels)
    for _, g in df.groupby("user_id"):
        g = g.sort_values("ts")
        assert g["split"].tolist() == ["train", "val", "test"]
    assert check_leakage(df, "split", "per_user_temporal")["temporal_order_ok"]


def test_leakage_check_detects_future_in_train(toy_interactions):
    df = toy_interactions.assign(split=global_temporal_split(toy_interactions, 0.2, 0.2))
    df.loc[df.index[-1], "split"] = "train"  # newest rating moved to train
    with pytest.raises(AssertionError):
        check_leakage(df, "split", "global_temporal")


def test_safe_extract_rejects_path_traversal(tmp_path):
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("../escape.txt", "x")
        zf.writestr("ok/file.txt", "y")
    out = tmp_path / "out"
    assert _safe_extract(zpath, ("ok/file.txt",), out)[0].read_text() == "y"
    with pytest.raises(ValueError):
        _safe_extract(zpath, ("../escape.txt",), out)
    assert not (tmp_path / "escape.txt").exists()
