"""Model comparison report: machine-readable JSON (used by the API/dashboard) + Markdown (Azerbaijani)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

LIMITATIONS = [
    "MovieLens 1M 2000–2003-cü illərin datasıdır; müasir zövqləri və kataloqu əks etdirmir.",
    "Reytinqlər explicit-dir (1–5 ulduz). Top-N modellərdə hər reytinq 'qarşılıqlı əlaqə' kimi götürülür; "
    "bu, real implicit feedback (baxış, klik) ilə eyni deyil.",
    "Relevant = test reytinqi ≥ 4. İstifadəçinin görmədiyi, amma bəyənəcəyi filmlər 'səhv' sayılır, "
    "ona görə mütləq metrik dəyərləri aşağı qiymətləndirilir (offline qiymətləndirmənin ümumi problemi).",
    "Qlobal temporal split realistikdir, amma validation dövründə istifadəçilərin yarıdan çoxu yenidir "
    "(test dövründə isə yeni istifadəçi azdır); warm test dəsti aktiv, uzunmüddətli istifadəçilərə doğru meyllidir.",
    "Tag-lər və IMDb/TMDB id-ləri ML-32M-dən gəlir (2005–2023, fərqli istifadəçi populyasiyası). "
    "Bu, sonradan yaranmış item metadatasıdır; bəzi tag-lər (məs. 'imdb top 250') populyarlıq siqnalı daşıyır.",
    "Hybrid çəkiləri və komponentləri validation-da seçildiyi üçün hybrid-in validation nəticəsi optimistdir; "
    "qərəzsiz müqayisə test sütunlarıdır.",
    "Per-user temporal (ikinci) protokolda digər istifadəçilərin gələcək reytinqləri train-ə düşür; "
    "nəticələr yalnız robustness üçün göstərilir, model seçimində istifadə olunmur.",
    "Demoqrafik sahələr (yaş, cins, peşə) modellərdə istifadə edilmir.",
    "Offline metriklər onlayn keyfiyyətin (A/B test) əvəzi deyil.",
]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return str(obj)


def _fmt(v: Any, digits: int = 4) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if isinstance(v, (int, np.integer)):
        return f"{v:,}"
    return f"{v:.{digits}f}"


def _m(entry: dict[str, Any], part: str, key: str, section: str = "metrics") -> Any:
    return entry.get(part, {}).get(section, {}).get(key)


def write_markdown(report: dict[str, Any], path: Path) -> None:
    metric = report["protocol"]["primary_metric"]
    models = report["models"]
    order = [r["model"] for r in report["selection"]["ranking"]]
    sel = report["selection"]["selected"]
    k0 = min(report["protocol"]["k_values"])
    kmax = max(report["protocol"]["k_values"])
    lines = [
        "# Model müqayisə hesabatı",
        "",
        f"Yaradılıb: {report['generated_at']} · seed {report['seed']} · ümumi müddət "
        f"{report['total_seconds'] / 60:.1f} dəq" + (" · **QUICK MODE (tam grid deyil)**" if report["quick_mode"]
                                                     else ""),
        "",
        "Bütün rəqəmlər `recsys train` tərəfindən real MovieLens 1M datası üzərində ölçülüb.",
        "",
        "## Seçilmiş model",
        "",
        f"**{sel}** — qayda: {report['selection']['rule']}.",
        "",
        "## Protokol",
        "",
        f"- Əsas split: **{report['dataset']['split_strategy']}** (80/10/10, zaman kəsiyi ilə). "
        "Modellər `train`-də öyrədilir, hiperparametrlər `val`-da seçilir, ən yaxşı konfiqurasiya `train+val` "
        "üzərində yenidən öyrədilib `test`-də **bir dəfə** qiymətləndirilir.",
        f"- Relevant: held-out reytinq ≥ {report['protocol']['relevance_threshold']}. "
        "İstifadəçinin artıq gördüyü filmlər namizədlərdən çıxarılır.",
        f"- Əsas metrik: `{metric}`; 95% CI istifadəçilər üzrə bootstrap ilə "
        f"({report['protocol']['bootstrap_samples']} nümunə).",
        "- Task ölçüləri (istifadəçi sayı): "
        + ", ".join(f"`{k}`={v}" for k, v in report["protocol"]["tasks"].items()),
        "",
        "## Warm istifadəçilər — əsas cədvəl",
        "",
        f"| Model | Ailə | val {metric} | test {metric} (95% CI) | test P@{k0} | test Recall@{kmax} | "
        f"test MAP@{k0} | test HR@{k0} | coverage@{k0} | ILD@{k0} | novelty@{k0} |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name in order:
        e = models[name]
        ci = e.get("test", {}).get("ci95", {}).get(metric)
        ci_txt = f" [{ci[0]:.4f}, {ci[1]:.4f}]" if ci else ""
        bold = "**" if name == sel else ""
        lines.append(
            f"| {bold}{name}{bold} | {e['family']} | {_fmt(_m(e, 'val', metric))} | "
            f"{_fmt(_m(e, 'test', metric))}{ci_txt} | {_fmt(_m(e, 'test', f'precision@{k0}'))} | "
            f"{_fmt(_m(e, 'test', f'recall@{kmax}'))} | {_fmt(_m(e, 'test', f'map@{k0}'))} | "
            f"{_fmt(_m(e, 'test', f'hit_rate@{k0}'))} | "
            f"{_fmt(_m(e, 'test', f'coverage@{k0}', 'beyond'), 3)} | {_fmt(_m(e, 'test', f'ild@{k0}', 'beyond'), 3)} | "
            f"{_fmt(_m(e, 'test', f'novelty@{k0}', 'beyond'), 2)} |"
        )
    skipped = [n for n, e in models.items() if "skipped" in e]
    if skipped:
        lines += ["", "Ötürülən modellər: " + ", ".join(f"{n} ({models[n]['skipped']})" for n in skipped)]

    cold_names = sorted({k for e in models.values() for k in e.get("test_cold", {})},
                        key=lambda s: int(s.rsplit("n", 1)[-1]))
    lines += [
        "",
        "## Cold-start (test dövründə yeni istifadəçilər)",
        "",
        "`nX` = istifadəçinin ilk X real reytinqi tarixçə kimi verilir, qalanı proqnozlaşdırılır. "
        "`n0` yalnız populyarlıq / onboarding ilə xidmət oluna bilər.",
        "",
        "| Model | " + " | ".join(f"{c} {metric}" for c in cold_names) + " |",
        "|---|" + "---|" * len(cold_names),
    ]
    for name in order:
        e = models[name]
        lines.append(f"| {name} | " + " | ".join(_fmt(_m({"x": e.get("test_cold", {}).get(c, {})}, "x", metric))
                                                 for c in cold_names) + " |")
    new_item = [(n, models[n].get("test", {}).get(f"new_item_recall@{kmax}")) for n in order]
    if any(v is not None for _, v in new_item):
        n_rel = next((models[n]["test"].get("new_item_relevant") for n in order if "test" in models[n]), 0)
        lines += [
            "",
            f"### Yeni filmlər (train-də reytinqi olmayan, test-də relevant: {n_rel})",
            "",
            f"| Model | new-item Recall@{kmax} |",
            "|---|---|",
            *[f"| {n} | {_fmt(v)} |" for n, v in new_item],
        ]

    rating_rows = [(n, models[n]["rating"]) for n in order if "rating" in models[n]]
    if rating_rows:
        lines += [
            "",
            "## Reytinq proqnozu (explicit modellər)",
            "",
            "| Model | val RMSE | val MAE | test RMSE | test MAE | test RMSE (warm) |",
            "|---|---|---|---|---|---|",
            *[f"| {n} | {_fmt(r['val']['rmse'])} | {_fmt(r['val']['mae'])} | {_fmt(r['test']['rmse'])} | "
              f"{_fmt(r['test']['mae'])} | {_fmt(r['test']['rmse_warm'])} |" for n, r in rating_rows],
            "",
            "Qeyd: aşağı RMSE yaxşı top-N sıralaması demək deyil — explicit modellər 'nə qədər bəyənəcək' "
            "sualına, top-N modellər 'nəyi seçəcək' sualına cavab verir.",
        ]

    lines += [
        "",
        "## Segmentlər (test, warm)",
        "",
        "| Model | light ndcg@10 | heavy ndcg@10 | light istifadəçi | heavy istifadəçi |",
        "|---|---|---|---|---|",
    ]
    for name in order:
        seg = models[name].get("test", {}).get("segments", {})
        lines.append(f"| {name} | {_fmt(seg.get('light', {}).get('ndcg@10'))} | "
                     f"{_fmt(seg.get('heavy', {}).get('ndcg@10'))} | {seg.get('light', {}).get('n_users', '—')} | "
                     f"{seg.get('heavy', {}).get('n_users', '—')} |")

    lines += [
        "",
        "## Robustness: per-user temporal split (seçimdə istifadə olunmur)",
        "",
        f"| Model | {metric} | recall@{kmax} |",
        "|---|---|---|",
        *[f"| {n} | {_fmt(_m(models[n], 'secondary_test', metric))} | "
          f"{_fmt(_m(models[n], 'secondary_test', f'recall@{kmax}'))} |" for n in order],
        "",
        "## Hybrid",
        "",
    ]
    hyb = models.get("hybrid", {})
    if hyb:
        bp = hyb["best_params"]
        lines += [
            f"Komponentlər: CF = `{bp['cf']}`, content = `{bp['cb']}`, popularity. "
            f"Warm həddi: ≥ {bp['warm_min_history']} reytinq.",
            "",
            "| Bucket | w_cf | w_cb | w_pop |",
            "|---|---|---|---|",
            *[f"| {b} | {w['cf']} | {w['cb']} | {w['pop']} |" for b, w in bp["weights"].items()],
            "",
            hyb.get("note", ""),
        ]

    lines += ["", "## Ən yaxşı hiperparametrlər", "",
              "Explicit modellər (bias_baseline, biased_mf) öz hədəfləri — validation RMSE ilə seçilir; "
              f"qalanları validation `{metric}` ilə.", "",
              "| Model | Parametrlər | Seçim meyarı | Grid ölçüsü |", "|---|---|---|---|"]
    for name in order:
        e = models[name]
        lines.append(f"| {name} | `{json.dumps(e.get('best_params', {}), default=_json_default)}` | "
                     f"{e.get('tuned_on', '—')} | {len(e.get('grid', [])) or '—'} |")

    lines += ["", "## Limitlər", "", *[f"- {x}" for x in LIMITATIONS], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_reports(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {**report, "limitations": LIMITATIONS}
    (reports_dir / "model_comparison.json").write_text(json.dumps(report, indent=2, default=_json_default),
                                                       encoding="utf-8")
    write_markdown(report, reports_dir / "model_comparison.md")
