# Dataset və preprocessing

Bütün rəqəmlər `recsys preprocess` tərəfindən real datadan hesablanıb (`artifacts/reports/eda.json`, `data/processed/manifest.json`, `data/processed/validation_report.json`).

## Mənbələr

| Fayl | Mənbə | Ölçü | MD5 | İstifadə |
|---|---|---|---|---|
| `ml-1m.zip` | https://files.grouplens.org/datasets/movielens/ml-1m.zip | ~6 MB | `c4d9eecfca2ab87c1945afe126590906` | reytinqlər, filmlər, istifadəçilər |
| `ml-32m.zip` | https://files.grouplens.org/datasets/movielens/ml-32m.zip | ~239 MB | `d472be332d4daa821edc399621853b57` | yalnız `links.csv`, `tags.csv`, `movies.csv` (metadata zənginləşdirməsi) |

- MD5 GroupLens-in `.md5` faylı ilə yoxlanır. Fayllar bir dəfə yüklənir, `data/raw/` qovluğunda qalır.
- GroupLens lisenziyası datanın yenidən paylaşılmasına icazə vermir, ona görə `data/` git-ə düşmür (`.gitignore`).
- **Mock/uydurma data yoxdur.** Unit testlərdəki kiçik cədvəllər yalnız testlərin içində yaradılır və `data/`-ya yazılmır.

## Niyə ML-1M (100K yox)?

Maşında 32 GB RAM var; ML-1M (1 000 209 reytinq) bütün modellər üçün rahat sığır (ən böyük sıx matris: 3883×3883 item-item). Daha çox istifadəçi və daha uzun zaman aralığı temporal split-i mənalı edir.

## Əsas statistika

| Göstərici | Dəyər |
|---|---|
| İstifadəçi | 6 040 (hər biri ≥ 20 reytinq) |
| Kataloq | 3 883 film; 3 706 reytinqli, **177 reytinqsiz** (real cold item) |
| Reytinq | 1 000 209 (1–5, tam ulduz) |
| Sparsity | 95.74% |
| Orta reytinq | 3.58 (std 1.12); reytinqlərin 57.5%-i ≥ 4 |
| İstifadəçi başına | min 20 / median 96 / max 2 314 |
| Film başına | min 1 / median 123.5 / max 3 428 |
| Populyarlıq Gini | 0.650 |
| Zaman | 2000-04-25 — 2003-02-28; reytinqlərin 90.5%-i 2000-ci ildə |

## Validasiya (record-level)

Hər qayda ayrıca sayılır; heç bir sətir səssizcə dəyişdirilmir.

| Qayda | Silinən |
|---|---|
| boş dəyər | 0 |
| tam olmayan reytinq | 0 |
| 1–5 xaricində reytinq | 0 |
| zaman 1995–2004 xaricində | 0 |
| naməlum film / istifadəçi | 0 / 0 |
| təkrarlanan (user, item) — sonuncu saxlanır | 0 |

ML-1M təmiz datasetdir, ona görə heç nə silinmir. Validasiya kodu yenə də işləyir və unit testlərlə yoxlanılır (`tests/unit/test_data.py` — hər qayda üçün süni pis sətirlər).

Film səviyyəsində: boş başlıq/ID təkrarı yoxdur. 1 333 filmin tag-i yoxdur (bayraq kimi qeyd olunur, silinmir).

## Feature engineering

- **Başlıq:** il çıxarılır (`Toy Story (1995)` → 1995), sonda olan artikl önə keçir (`Matrix, The` → `The Matrix`, `Postman, The (Postino, Il)` → `The Postman (Il Postino)`).
- **Janrlar:** 18 janr, multi-hot matris (diversity metrikası və onboarding üçün).
- **Tag-lər (ML-32M):** film başına fərqli istifadəçilərin sayı ≥ 2 olan tag-lər, ən çox 25. 
- **ID uyğunluğu ML-1M ↔ ML-32M:** eyni `movieId` + tolerant başlıq yoxlaması (alternativ başlıqlar, alt-başlıq, ±1 il) → 3 756 film; ID uyğun gəlmədikdə unikal başlıq+il → 10 film; **117 film uyğunlaşmadı** (onlara tag verilmir). Nəticədə 2 550 filmin tag-i var.
- **Mətn sənədi** (content modelləri üçün): `"Toy Story. 1995. Genres: Animation, Children's, Comedy. Tags: pixar, animation, ..."`.
- **Populyarlıq statistikası** yalnız o anda train sayılan hissədən hesablanır (leakage yoxdur).
- **Sparse matrislər:** `data/processed/matrices/{train,train_val,all}.npz` (CSR, float32).

## Split

### Əsas: qlobal temporal (80 / 10 / 10)

Bir zaman kəsiyi bütün istifadəçilər üçün. Eyni saniyəli reytinqlər həmişə eyni hissəyə düşür.

| Hissə | Reytinq | İstifadəçi | Warm | Cold | Yeni film | Tarix |
|---|---|---|---|---|---|---|
| train | 800 164 | 5 400 | — | — | — | 2000-04-25 — 2000-12-02 |
| val | 100 024 | 1 134 | 523 | 611 | 16 | 2000-12-02 — 2000-12-29 |
| test | 100 021 | 1 209 | 1 180 | 29 | 28 | 2000-12-29 — 2003-02-28 |

"Warm" = modelin öyrəndiyi hissədə tarixçəsi var (val üçün train; test üçün train+val). Leakage yoxlaması avtomatikdir: `max(train.ts) < min(val.ts)`, `max(val.ts) < min(test.ts)`, heç bir (user, item) iki hissədə yoxdur; pozulduqda pipeline dayanır.

### İkinci: istifadəçi daxili temporal (robustness)

Hər istifadəçinin son 10%-i test, ondan əvvəlki 10%-i val (800 309 / 99 950 / 99 950). Hər istifadəçi qiymətləndirilir, amma başqa istifadəçilərin gələcək reytinqləri train-ə düşür. Nəticələr ayrıca göstərilir və model seçimində istifadə olunmur.

## Məhdudiyyətlər

- 2000–2003 dövrü; müasir kataloq və zövqlər yoxdur.
- Reytinqlər explicit-dir; top-N modellər onları "qarşılıqlı əlaqə" kimi qəbul edir.
- Posterlər və film təsvirləri yoxdur. UI posterləri lokal generasiya edir və bunu açıq yazır.
- Tag-lər fərqli populyasiyadan və sonrakı illərdən gəlir; bəziləri populyarlıq siqnalı daşıyır (məs. `imdb top 250`).
- Demoqrafik sahələr (`users.dat`) yalnız saxlanır, modellərdə istifadə olunmur.
- Test dövründə cəmi 29 tam yeni istifadəçi var — test cold-start nəticələri səs-küylüdür; validation-da 611 cold istifadəçi var.
