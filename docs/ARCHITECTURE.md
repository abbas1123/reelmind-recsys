# Arxitektura

## Qatlar

```
frontend/ (React + TS + Vite + Tailwind v4 + HeroUI v3)
   │  HTTP /api  (Vite proxy → 127.0.0.1:8010)
backend/app/ (FastAPI + Pydantic + SQLAlchemy/SQLite)      ← veb qatı: profillər, reytinqlər, favoritlər
   │  Python çağırışı (RecommendationEngine)
backend/recsys/inference/  (engine, cold_start)            ← inference interfeysi, FastAPI-dən asılı deyil
   │  joblib / npy artifaktları
backend/recsys/training/ + evaluation/ + models/           ← tuning, qiymətləndirmə, modellər
   │  parquet + npz
backend/recsys/data/ (adapters, validate, split, eda)      ← data pipeline
   │
data/raw (MovieLens zip-ləri)  →  data/processed  →  artifacts/
```

Qaydalar:

- `recsys` paketi `fastapi`/`app` import etmir. Eyni engine CLI-da (`recsys recommend`), testlərdə və API-də işləyir.
- Model artifaktları bir dəfə öyrədilir və `artifacts/models/serving/` qovluğunda saxlanır. API başlayanda yalnız yükləyir, yenidən öyrətmir.
- Bütün metriklər `artifacts/reports/model_comparison.json`-dadır. API onu dəyişmədən qaytarır, dashboard yalnız onu göstərir.

## Data axını

1. `recsys download` — `ml-1m.zip` və `ml-32m.zip` GroupLens-dən bir dəfə yüklənir, MD5 yoxlanır, yalnız lazımi fayllar çıxarılır (zip-slip qorunması ilə).
2. `recsys preprocess` — `DatasetAdapter` raw faylları kanonik cədvəllərə çevirir → validasiya → indekslər → split → leakage yoxlaması → parquet/npz → EDA.
3. `recsys train` — grid search (val) → test (bir dəfə) → hybrid tuning → seçim → serving modelləri (bütün data) → hesabat.
4. `recsys serve` — FastAPI engine-i yükləyir.

## Model interfeysi

`recsys/models/base.py`:

```python
class Recommender:
    def fit(self, X, items=None, ts=None): ...          # X: user × item reytinq matrisi (CSR)
    def score(self, history, user_idx=None): ...        # dense skorlar (n_rows × n_items)
    def predict(self, user_idx, item_idx): ...          # yalnız explicit modellər (RMSE/MAE)
```

- `history` — istifadəçi sətirləri. `user_idx=None` olduqda model **fold-in** edir: yeni istifadəçini yenidən öyrətmədən tarixçəsindən hesablayır (EASE/ItemKNN: `x·W`, PureSVD: `x·V·Vᵀ`, iALS: bir ALS addımı, BiasedMF: bir ridge həlli).
- `ts` — eyni sparsity-də timestamp matrisi; hazırda yalnız trending popularity istifadə edir.
- Bütün modellər `registry.py`-də qeydiyyatdadır; grid-lər `configs/default.yaml`-dadır.

## Hybrid və cold-start

```
s(u,i) = w_cf·minmax(s_cf) + w_cb·minmax(s_cb) + w_pop·minmax(s_pop)
bucket: 0 reytinq → cold | 1..4 → light | ≥5 → warm   (hər bucket-in öz çəkiləri)
```

- `warm` çəkiləri ≥ 5 reytinqli warm validation istifadəçilərində tənzimlənir. `light` çəkiləri 1–4 reytinqli bütün validation sətirlərində tənzimlənir: simulyasiya olunmuş yeni istifadəçilər (ilk 1 və ya 3 real reytinq) və tarixçəsi qısa olan warm istifadəçilər birlikdə.
- `cold` (0 reytinq): `cold_start.py` — log-populyarlıq + damped orta reytinq, onboarding janrlarına görə affinity, MMR ilə janr müxtəlifliyi. Janr hissəsi heuristic-dir (data ilə tənzimlənməyib) və sənəddə belə qeyd olunub.
- Yeni film (heç kim reytinq verməyib): content oxşarlığı bütün kataloqu əhatə edir, ona görə belə filmlər "Similar" siyahılarında və content/hybrid skorlarında görünə bilir.

## Yeni domen əlavə etmək (məs. kitablar)

1. `recsys/data/adapters/books.py` yaradın:

```python
@register
class GoodbooksAdapter(DatasetAdapter):
    name = "goodbooks-10k"
    domain = "book"

    def load(self, raw_dir):
        books = pd.read_csv(raw_dir / "goodbooks-10k" / "books.csv")
        ratings = pd.read_csv(raw_dir / "goodbooks-10k" / "ratings.csv")
        items = pd.DataFrame({
            "item_id": books["book_id"], "domain": self.domain,
            "title": books["title"], "raw_title": books["title"],
            "year": books["original_publication_year"].astype("Int64"),
            "genres": [[] for _ in range(len(books))], "tags": [[] for _ in range(len(books))],
            "external_ids": [{"isbn": i} for i in books["isbn"]],
        })
        items["text"] = [self.build_text(t, y, g, tg) for t, y, g, tg in
                         zip(items.title, items.year, items.genres, items.tags)]
        inter = ratings.rename(columns={"book_id": "item_id"}).assign(ts=0)  # timestamp yoxdursa
        return RawDataset(items=items, interactions=inter[["user_id", "item_id", "rating", "ts"]])
```

2. `adapters/__init__.py`-də import edin, `configs/default.yaml`-da `dataset.name: goodbooks-10k` yazın.
3. Timestamp yoxdursa `split.strategy: per_user_temporal` əvəzinə təsadüfi split əlavə etmək lazımdır (hazırda yalnız temporal strategiyalar var — bu, bilərəkdən edilib).
4. Qalan hər şey (validasiya, modellər, hesabat, API, frontend) dəyişmədən işləyir. DB-dəki `items.domain` sütunu və frontend-dəki generic `Item` tipi domen üçün hazırdır; domenə xas kart dizaynı üçün `MovieCard` əvəzinə `BookCard` əlavə edilə bilər.

## API xülasəsi

Tam sənəd: `http://127.0.0.1:8010/docs` (OpenAPI).

| Qrup | Endpoint-lər |
|---|---|
| Profil | `GET/POST /api/users`, `GET/DELETE /api/users/{id}`, `POST /api/users/from-movielens/{ml_user_id}` |
| Onboarding | `GET /api/genres`, `GET /api/onboarding/candidates`, `PUT /api/users/{id}/preferences` |
| Tövsiyə | `GET /api/users/{id}/recommendations?k=&genre=&strategy=hybrid\|cf\|content\|popularity` |
| Kəşf | `GET /api/items/trending`, `GET /api/items/top-rated`, `GET /api/genres/{g}/items` |
| Axtarış | `GET /api/search?q=&mode=keyword\|semantic&genre=&year_from=&year_to=` |
| Film | `GET /api/items/{id}`, `GET /api/items/{id}/similar?mode=hybrid\|collaborative\|content` |
| Fəaliyyət | `PUT/DELETE /api/users/{id}/ratings/{item}`, `PUT/DELETE /api/users/{id}/favorites/{item}`, `POST /api/users/{id}/interactions`, `GET .../ratings`, `.../favorites`, `.../history` |
| Model | `GET /api/model/info`, `GET /api/model/evaluation`, `GET /api/model/eda`, `GET /api/health` |

## Frontend dizayn sistemi

"Lokal sinemateka" konsepti — şablon görünüşündən qaçmaq üçün tipografiya mərkəzli editorial dizayn:

- **Tipografiya:** başlıqlar `Instrument Serif`, mətn `Inter Tight`, rəqəmlər və etiketlər `IBM Plex Mono`. Fontlar `@fontsource` paketləri ilə bundle olunur (offline işləyir).
- **Rəng:** iki tema — "Ink" (isti qara, default) və "Paper" (isti kağız). Tək accent rəngi amber. Tokenlər `src/index.css`-də; HeroUI v3 tokenləri (`--accent`, `--background`, `--radius` ...) bu palitraya bağlanıb, ona görə HeroUI komponentləri (Button, SearchField, TextField, ToggleButtonGroup, Tabs, Skeleton, Spinner) eyni dili danışır.
- **Cover-lar:** MovieLens-də poster yoxdur. `CoverArt` hər film üçün janr tonundan (film-stock rəngləri), film id-sinin hash-indən seçilən həndəsi motivdən (dairə, zolaqlar, diaqonal, halqalar, sütun) və serif başlıqdan "tipografik cover" qurur. Real şəkil olmadığı UI-da açıq yazılır.
- **Qrafiklər:** kateqorial palitra (amber, teal, bənövşəyi, qırmızı) hər iki tema üçün ayrıca seçilib və dataviz validatoru ilə yoxlanıb (CVD ayrılması, kontrast, lightness band — hamısı PASS). Bütün qrafiklərdə tooltip, legend və eyni rəqəmləri göstərən cədvəl var.
- **Layout:** hairline xətlər, nömrələnmiş bölmələr (`01`, `02` ...), Fig./Table nömrələri, mono rəqəmlər; 375 px-dən geniş ekranlarda horizontal scroll yoxdur.
