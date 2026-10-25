"""Exploratory data analysis: summary statistics (JSON), charts (PNG) and a Markdown report."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from recsys.data.dataset import ProcessedData  # noqa: E402

log = logging.getLogger(__name__)

# Reference palette (light mode) — single-series charts use slot 1.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"
SERIES_3 = "#1baf7a"


def gini(values: np.ndarray) -> float:
    """Gini coefficient of a non-negative distribution (0 = equal, 1 = concentrated)."""
    v = np.sort(np.asarray(values, dtype=np.float64))
    if v.sum() == 0:
        return 0.0
    n = len(v)
    cum = np.cumsum(v)
    return float((n + 1 - 2 * (cum / cum[-1]).sum()) / n)


def summarize(data: ProcessedData) -> dict[str, Any]:
    df = data.interactions
    per_user = df.groupby("user_id").size()
    per_item = df.groupby("item_id").size()
    rated_items = per_item.index.nunique()
    genres = pd.Series([g for gs in data.items["genres"] for g in gs]).value_counts()
    ts = pd.to_datetime(df["ts"], unit="s", utc=True)

    def split_stats(col: str) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name in ("train", "val", "test"):
            # "Warm" means the user has history in everything the model trains on before this split.
            history = df[df[col].isin({"train": [], "val": ["train"], "test": ["train", "val"]}[name])]
            train_users, train_items = set(history["user_id"]), set(history["item_id"])
            part = df[df[col] == name]
            users = set(part["user_id"])
            entry: dict[str, Any] = {
                "interactions": len(part),
                "users": len(users),
                "items": int(part["item_id"].nunique()),
                "ts_min": str(pd.to_datetime(part["ts"].min(), unit="s", utc=True).date()) if len(part) else None,
                "ts_max": str(pd.to_datetime(part["ts"].max(), unit="s", utc=True).date()) if len(part) else None,
            }
            if name != "train":
                entry["warm_users"] = len(users & train_users)
                entry["cold_users"] = len(users - train_users)
                entry["new_items"] = len(set(part["item_id"]) - train_items)
                entry["relevant_interactions"] = int((part["rating"] >= 4).sum())
            out[name] = entry
        return out

    return {
        "n_users": data.n_users,
        "n_items_catalog": data.n_items,
        "n_items_rated": int(rated_items),
        "n_items_unrated": int(data.n_items - rated_items),
        "n_interactions": len(df),
        "density": len(df) / (data.n_users * data.n_items),
        "sparsity": 1 - len(df) / (data.n_users * data.n_items),
        "rating_mean": float(df["rating"].mean()),
        "rating_std": float(df["rating"].std()),
        "rating_distribution": {str(int(k)): int(v) for k, v in df["rating"].value_counts().sort_index().items()},
        "positive_share": float((df["rating"] >= 4).mean()),
        "ratings_per_user": {"min": int(per_user.min()), "median": float(per_user.median()),
                             "mean": float(per_user.mean()), "max": int(per_user.max())},
        "ratings_per_item": {"min": int(per_item.min()), "median": float(per_item.median()),
                             "mean": float(per_item.mean()), "max": int(per_item.max())},
        "item_popularity_gini": gini(np.concatenate([per_item.to_numpy(), np.zeros(data.n_items - rated_items)])),
        "top_1pct_items_share": float(per_item.sort_values(ascending=False).head(max(1, rated_items // 100)).sum()
                                      / len(df)),
        "genre_counts": {k: int(v) for k, v in genres.items()},
        "time_range": {"min": str(ts.min().date()), "max": str(ts.max().date())},
        "ratings_by_year": {str(k): int(v) for k, v in ts.dt.year.value_counts().sort_index().items()},
        "items_with_tags": int(data.items["tags"].map(len).gt(0).sum()),
        "split_primary": split_stats("split"),
        "split_secondary": split_stats("split_user"),
    }


def _style(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, color=INK_2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK_2, fontsize=9)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def _save(fig: plt.Figure, path: Path) -> str:
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path.name


def make_charts(data: ProcessedData, out_dir: Path) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = data.interactions
    files = []

    fig, ax = plt.subplots(figsize=(6, 3.4))
    dist = df["rating"].value_counts().sort_index()
    ax.bar(dist.index.astype(int).astype(str), dist.to_numpy(), color=SERIES_1, width=0.6)
    for x, v in zip(dist.index.astype(int).astype(str), dist.to_numpy(), strict=True):
        ax.text(x, v, f"{v / len(df):.0%}", ha="center", va="bottom", fontsize=8, color=INK_2)
    _style(ax, "Rating distribution", "Rating (stars)", "Ratings")
    files.append(_save(fig, out_dir / "rating_distribution.png"))

    fig, ax = plt.subplots(figsize=(6, 3.4))
    per_user = df.groupby("user_id").size()
    bins = np.logspace(np.log10(per_user.min()), np.log10(per_user.max()), 40)
    ax.hist(per_user, bins=bins, color=SERIES_1, edgecolor=SURFACE, linewidth=1)
    ax.set_xscale("log")
    _style(ax, "Ratings per user (log scale)", "Ratings per user", "Users")
    files.append(_save(fig, out_dir / "ratings_per_user.png"))

    fig, ax = plt.subplots(figsize=(6, 3.4))
    per_item = df.groupby("item_id").size().sort_values(ascending=False).to_numpy()
    ax.plot(np.arange(1, len(per_item) + 1), per_item, color=SERIES_1, linewidth=2)
    ax.set_yscale("log")
    _style(ax, "Item popularity long tail", "Item rank", "Ratings (log)")
    files.append(_save(fig, out_dir / "item_long_tail.png"))

    fig, ax = plt.subplots(figsize=(6, 4.2))
    genres = pd.Series([g for gs in data.items["genres"] for g in gs]).value_counts().sort_values()
    ax.barh(genres.index, genres.to_numpy(), color=SERIES_1, height=0.6)
    _style(ax, "Movies per genre (catalog)", "Movies", "")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.grid(axis="y", visible=False)
    files.append(_save(fig, out_dir / "genre_counts.png"))

    fig, ax = plt.subplots(figsize=(7, 3.4))
    month = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_localize(None).dt.to_period("M")
    monthly = month.value_counts().sort_index()
    ax.bar(monthly.index.to_timestamp(), monthly.to_numpy(), width=25, color=SERIES_1)
    for name, color in (("val", SERIES_2), ("test", SERIES_3)):
        cut = pd.to_datetime(df.loc[df["split"] == name, "ts"].min(), unit="s")
        ax.axvline(cut, color=color, linewidth=2, linestyle="--", label=f"{name} starts {cut.date()}")
    ax.set_yscale("log")
    ax.legend(frameon=False, fontsize=8, labelcolor=INK_2)
    _style(ax, "Ratings per month and temporal split cuts", "Month", "Ratings (log)")
    files.append(_save(fig, out_dir / "ratings_over_time.png"))
    return files


def write_report(summary: dict[str, Any], charts: list[str], validation: dict[str, Any], path: Path) -> None:
    s = summary
    p = s["split_primary"]
    lines = [
        "# EDA hesabatı — MovieLens 1M",
        "",
        "Bu fayl `recsys preprocess` tərəfindən avtomatik yaradılır. Bütün rəqəmlər real datadan hesablanıb.",
        "",
        "## Əsas göstəricilər",
        "",
        "| Göstərici | Dəyər |",
        "|---|---|",
        f"| İstifadəçi | {s['n_users']:,} |",
        f"| Kataloqdakı film | {s['n_items_catalog']:,} |",
        f"| Reytinqi olan film | {s['n_items_rated']:,} |",
        f"| Reytinqsiz film (real cold item) | {s['n_items_unrated']:,} |",
        f"| Reytinq | {s['n_interactions']:,} |",
        f"| Sparsity | {s['sparsity']:.4%} |",
        f"| Orta reytinq | {s['rating_mean']:.3f} (std {s['rating_std']:.3f}) |",
        f"| Reytinq ≥ 4 payı | {s['positive_share']:.1%} |",
        f"| İstifadəçi başına reytinq (min / median / max) | {s['ratings_per_user']['min']} / "
        f"{s['ratings_per_user']['median']:.0f} / {s['ratings_per_user']['max']} |",
        f"| Film başına reytinq (min / median / max) | {s['ratings_per_item']['min']} / "
        f"{s['ratings_per_item']['median']:.0f} / {s['ratings_per_item']['max']} |",
        f"| Populyarlıq Gini | {s['item_popularity_gini']:.3f} |",
        f"| Ən populyar 1% filmin reytinq payı | {s['top_1pct_items_share']:.1%} |",
        f"| Tag-i olan film (ML-32M) | {s['items_with_tags']:,} |",
        f"| Zaman aralığı | {s['time_range']['min']} — {s['time_range']['max']} |",
        "",
        "## Validasiya",
        "",
        f"Daxil olan reytinq: {validation['interactions']['input_rows']:,}; "
        f"qalan: {validation['interactions']['output_rows']:,}.",
        "",
        "| Qayda | Silinən sətir |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in validation["interactions"]["rules"].items()],
        "",
        "## Split (əsas: qlobal temporal)",
        "",
        "| Hissə | Reytinq | İstifadəçi | Warm istifadəçi | Cold istifadəçi | Yeni film | Tarix |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in ("train", "val", "test"):
        e = p[name]
        lines.append(
            f"| {name} | {e['interactions']:,} | {e['users']:,} | {e.get('warm_users', '—')} | "
            f"{e.get('cold_users', '—')} | {e.get('new_items', '—')} | {e['ts_min']} — {e['ts_max']} |"
        )
    lines += [
        "",
        "Qeyd: MovieLens 1M reytinqlərinin böyük hissəsi 2000-ci ilə aiddir. Qlobal zaman kəsiyi "
        "validation dövründə çoxlu yeni (cold) istifadəçi yaradır (test dövründə azdır). Onlar ayrıca cold-start protokolu ilə qiymətləndirilir.",
        "",
        "## Qrafiklər",
        "",
        *[f"![{c}](eda/{c})" for c in charts],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_eda(data: ProcessedData, reports_dir: Path, validation: dict[str, Any]) -> dict[str, Any]:
    summary = summarize(data)
    charts = make_charts(data, reports_dir / "eda")
    (reports_dir / "eda.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(summary, charts, validation, reports_dir / "eda.md")
    log.info("EDA written to %s", reports_dir / "eda.md")
    return summary
