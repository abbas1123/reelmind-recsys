# ReelMind — lokal AI tövsiyə sistemi

MovieLens 1M üzərində qurulmuş, **tam lokal** işləyən film tövsiyə sistemi: real data pipeline, 11 öyrədilmiş və müqayisə edilmiş model, validation-a əsaslanan hybrid, cold-start, FastAPI backend, React frontend və dürüst qiymətləndirmə hesabatı. Bulud, pullu API və xarici inference yoxdur — internet yalnız datanın və embedding modelinin **bir dəfə** yüklənməsi üçün lazımdır.

> Ders layihəsi. Bütün rəqəmlər real datadan ölçülüb; heç bir metrik, nəticə və ya data uydurulmayıb.

## Nə edir

- **Data:** MovieLens 1M (1 000 209 reytinq, 6 040 istifadəçi, 3 883 film) + ML-32M-dən community tag-lər. MD5 yoxlaması, validasiya, EDA, leakage-siz temporal split.
- **Modellər:** Popularity (trending), Bias baseline, UserKNN, ItemKNN, PureSVD, iALS, EASE^R, Biased MF (ALS), TF-IDF content, lokal embedding content (`all-MiniLM-L6-v2`), Hybrid.
- **Qiymətləndirmə:** Precision/Recall/NDCG/MAP/HitRate/MRR @10/@20, RMSE/MAE, coverage, diversity (ILD), novelty, Gini, bootstrap 95% CI, cold-start simulyasiyası, ikinci (robustness) protokol.
- **Cold-start:** yeni istifadəçi (onboarding janrları + populyarlıq + MMR), az tarixçə (fold-in, yenidən öyrətmədən), yeni film (content oxşarlığı).
- **Tətbiq:** profil seçimi / real MovieLens istifadəçisi kimi baxış, onboarding, şəxsi "proqram", axtarış (keyword + lokal semantik), film səhifəsi, reytinq, favorit, tarixçə, qiymətləndirmə hesabatı (dashboard).

## Tələblər

| Alət | Yoxlanmış versiya |
|---|---|
| Windows 11 (Linux/macOS da işləməlidir, sınaqdan keçirilməyib) | 10.0.26200 |
| Python | 3.12.10 (`>=3.11,<3.14`) |
| [uv](https://docs.astral.sh/uv/) | 0.13.0 |
| Node.js / npm | 24.20.0 / 11.19.0 |
| Brauzer (e2e testlər üçün) | sistemdəki Microsoft Edge |

Yaddaş: ~3 GB RAM (training zamanı), ~1 GB disk (data + artifaktlar + embedding modeli). GPU lazım deyil.

## AI ilə quraşdırma

Repo-da AI agentləri üçün addım-addım təlimat var: [AGENTS.md](AGENTS.md) (Claude Code, Codex, Cursor, Copilot və s. onu avtomatik oxuyur). Öz AI köməkçinə sadəcə bunu yaz:

> Bu layihəni kompüterimdə quraşdır və işə sal: https://github.com/abbas1123/reelmind-recsys — repo-dakı AGENTS.md təlimatına addım-addım əməl et və hər addımın yoxlamasını et.

## Tez başlanğıc

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
```

`setup.ps1`: asılılıqlar → data yükləmə → embedding modeli → preprocess → training (~8 dəq, CPU) → DB → yoxlama. `dev.ps1`: backend (http://127.0.0.1:8010/docs) + frontend (http://127.0.0.1:5173).

### Addım-addım (əl ilə)

```powershell
cd backend
uv sync --extra embeddings          # Python asılılıqları (CPU torch)
uv run recsys download              # ML-1M + ML-32M, MD5 yoxlaması (~245 MB, bir dəfə)
uv run recsys download-models       # all-MiniLM-L6-v2 → artifacts/hf_cache (~90 MB, bir dəfə)
uv run recsys preprocess            # validasiya, split, EDA → data/processed, artifacts/reports/eda.md
uv run recsys download-posters      # Wikipedia posterləri → artifacts/posters (bir dəfə, açarsız; opsional)
uv run recsys train                 # tuning + test + hybrid + serving modelləri + hesabat
uv run recsys evaluate              # hesabatı göstər + saxlanmış modelləri yoxla
uv run recsys seed-db               # SQLite kataloq (API başlayanda avtomatik də olur)
uv run recsys serve                 # http://127.0.0.1:8010
uv run recsys recommend --user 42   # CLI-dan real istifadəçi üçün top-10
```

```powershell
cd frontend
npm install
npm run dev                         # http://127.0.0.1:5173 (/api → 8010 proxy)
```

Hamısı bir komanda ilə: `uv run recsys pipeline` (download → models → preprocess → train → seed-db). Posterlər yavaş olduğu üçün opsionaldır: `uv run recsys pipeline --posters` və ya sonradan ayrıca `uv run recsys download-posters`.

## Canlı demo linki (müvəqqəti)

```powershell
winget install --id Cloudflare.cloudflared       # bir dəfə
powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
```

Skript production build-i (port 4173) və ayrıca demo backend-i (port 8011, `data/demo.db`) qaldırır, sonra Cloudflare quick tunnel açır və `https://....trycloudflare.com` linkini çap edir. Link yalnız pəncərə açıq və kompüter işləyərkən aktivdir, hər dəfə yeni ünvan verilir. Ziyarətçilər profil yarada və reytinq verə bilər, amma sənin `data/app.db` bazana toxunmurlar. Ctrl+C hamısını dayandırır.

## Layihə strukturu

```
backend/
  configs/default.yaml     bütün parametrlər (seed, split, grid-lər, hybrid, embedding)
  recsys/                  ML paketi (FastAPI-dən asılı deyil)
    data/                  download, adapters (MovieLens), validate, split, eda, preprocess
    models/                popularity, knn, svd, ials, ease, explicit, content, hybrid, embeddings
    evaluation/            metrics, protocol, report
    training/              tune, train
    inference/             engine, cold_start
    cli.py                 `recsys` komandası
  app/                     FastAPI: main, db (SQLite), schemas, routers/
  tests/                   unit/, integration/ (real data), api/
frontend/
  src/                     React + TS + Tailwind v4 + HeroUI v3 (pages/, components/, api/)
  e2e/                     Playwright
docs/                      DATASET.md, EVALUATION.md, ARCHITECTURE.md, TROUBLESHOOTING.md
artifacts/reports/         eda.md, model_comparison.md/.json (git-də saxlanılır)
data/, artifacts/models/   yerli data və modellər (git-ə düşmür)
```

## Nəticələr

Son tam training (seed 42, CPU, 7.8 dəq). Əsas protokol: qlobal temporal split, test dəsti **bir dəfə** qiymətləndirilir, 1 159 warm istifadəçi.

| Model | val NDCG@10 | test NDCG@10 [95% CI] | test Recall@20 |
|---|---|---|---|
| **hybrid** (seçilib: iALS + TF-IDF + trending) | 0.1384 | **0.2347** [0.219, 0.250] | 0.1066 |
| ials | 0.1382 | 0.2267 [0.212, 0.241] | 0.1031 |
| ease | 0.1312 | 0.2192 [0.205, 0.234] | 0.1059 |
| user_knn | 0.1284 | 0.2186 [0.204, 0.234] | 0.0965 |
| item_knn | 0.1272 | 0.2155 [0.201, 0.231] | 0.0963 |
| pure_svd | 0.1291 | 0.2114 [0.197, 0.226] | 0.0980 |
| popularity (trending) | 0.1321 | 0.2071 [0.194, 0.220] | 0.1067 |
| content_tfidf | 0.0644 | 0.1302 [0.121, 0.141] | 0.0559 |
| content_embedding | 0.0596 | 0.1042 [0.095, 0.113] | 0.0479 |
| bias_baseline (RMSE 0.9198) | 0.0181 | 0.0437 [0.040, 0.048] | 0.0309 |
| biased_mf (RMSE 0.8951) | 0.0203 | 0.0433 [0.039, 0.048] | 0.0382 |

Əsas nəticələr: hybrid ən yaxşıdır, amma iALS ilə fərq kiçikdir (CI-lar üst-üstə düşür); trending popularity çox güclü baseline-dır; explicit modellər RMSE-də yaxşı, top-N-də zəifdir; per-user split-də sıralama dəyişir (EASE birinci) — ətraflı izah [docs/EVALUATION.md](docs/EVALUATION.md)-dədir.

Tam hesabat: [artifacts/reports/model_comparison.md](artifacts/reports/model_comparison.md) · metodologiya: [docs/EVALUATION.md](docs/EVALUATION.md) · data: [docs/DATASET.md](docs/DATASET.md).

## Testlər

```powershell
cd backend;  uv run pytest            # unit + integration (real data) + API
cd frontend; npm run test:e2e         # Playwright (backend + frontend avtomatik qalxır, ayrıca data/e2e.db)
```

Son yoxlama (bu maşında icra olunub):

| Test dəsti | Status | Nəyi yoxlayır |
|---|---|---|
| `tests/unit` (57) | ✅ keçdi | poster lookup parse, başlıq parse, validasiya qaydaları, split və leakage, zip-slip qorunması, metriklər (əllə hesablanmış nümunə + reference), hər model (oyuncaq data, fold-in, save/load, determinizm), hybrid switching, trending, `train --only` yoxlaması |
| `tests/integration` (9, real data) | ✅ keçdi | ML-1M sayları, temporal split, 177 reytinqsiz film, hesabatın düzgünlüyü, test metrikinin təkrar hesablanması, engine self-check, real istifadəçilər üçün tövsiyələr, fold-in, janr filtri, cold item |
| `tests/api` (19) | ✅ keçdi | poster endpoint, profil CRUD, naməlum janr filtrlərinin rədd edilməsi (422), onboarding və cold start (bütün strategiyalar), reytinqlərin tövsiyələri dəyişməsi, izahların yalnız bəyənilən filmə istinadı, validasiya xətaları, favorit/tarixçə, eyni anda gələn təkrar yazma sorğuları (500 yox), UTC vaxt damğaları, MovieLens profili, axtarış (keyword + semantik), oxşar filmlər, hesabatın dəyişmədən verilməsi, degraded rejim |
| `frontend/e2e` (5, Playwright + Edge) | ✅ keçdi | onboarding → cold → light tövsiyələr; axtarış → film → reytinq + favorit → My list; MovieLens istifadəçisi (warm); dashboard rəqəmləri = API hesabatı; lokal semantik axtarış |
| `ruff`, `tsc`, `vite build` | ✅ təmiz | lint, tip yoxlaması, production build |
| GPU (`--extra gpu`) | ⏸ sınaqdan keçirilməyib | CUDA 12.8 torch quraşdırılmayıb (lazım deyil) |
| Linux / macOS | ⏸ sınaqdan keçirilməyib | yalnız Windows 11-də işlədilib |

UI testləri ML-in düzgünlüyünə sübut sayılmır: data emalı, training və inference ayrıca pytest testləri ilə yoxlanılır (metriklər əllə hesablanmış nümunələrə qarşı, leakage yoxlamaları, saxlanmış modeldən hesabatdakı test metrikinin təkrar hesablanması).

## Konfiqurasiya

`backend/configs/default.yaml` — hər dəyər mühit dəyişəni ilə dəyişdirilə bilər: `RECSYS_SEED=7`, `RECSYS_EVALUATION__BOOTSTRAP_SAMPLES=200`, `RECSYS_PATHS__DB_PATH=data/other.db`. Başqa YAML: `RECSYS_CONFIG=path/to.yaml`.

## Offline və GPU

- Yükləmədən sonra hər şey offline işləyir: embedding modeli `artifacts/hf_cache/` qovluğundan `HF_HUB_OFFLINE=1` ilə yüklənir; posterlər `artifacts/posters/`-dan backend tərəfindən verilir; font (Plus Jakarta Sans) npm paketi kimi bundle olunur (Google Fonts sorğusu yoxdur).
- **Posterlər:** `recsys download-posters` IMDb id → Wikidata → İngilis Wikipedia səhifə şəkli yolu ilə bir dəfə yükləyir (API açarı lazım deyil). Wikimedia limitləri səbəbindən ~10–75 dəq çəkə bilər; aralıq nəticələr saxlanılır, təkrar işlədəndə qaldığı yerdən davam edir. Posterlər müəllif hüququ ilə qorunur: yalnız lokal, dərs məqsədli istifadə olunur, git-ə düşmür. Posteri olmayan filmlər üçün UI janr rəngindən artwork çəkir.
- Default CPU. GPU (opsional): `uv sync --extra gpu` (PyTorch CUDA 12.8, RTX 50xx üçün lazımdır), `embeddings.device: auto`. **GPU yolu bu maşında sınaqdan keçirilməyib** — CPU-da 3 883 filmin embedding-i ~17 s çəkir, ona görə ehtiyac yoxdur.

## Yeni domen (musiqi, kitab, oyun)

Yeni `DatasetAdapter` yazmaq kifayətdir — qalan pipeline, modellər, API və UI dəyişmir. Nümunə və addımlar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#yeni-domen-əlavə-etmək-məs-kitablar).

## Problemlər

[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md): SSL (korporativ proxy), port məşğulluğu, embedding modeli, GPU, Playwright brauzeri.

## Lisenziya və mənbələr

- Kod: ders məqsədli.
- Data: F. Maxwell Harper and Joseph A. Konstan. 2015. *The MovieLens Datasets: History and Context.* ACM TiiS 5(4). GroupLens şərtlərinə görə data yenidən paylaşılmır.
- Embedding modeli: `sentence-transformers/all-MiniLM-L6-v2` (Apache 2.0).
