# Model müqayisə hesabatı

Yaradılıb: 2026-10-25T13:19:27+00:00 · seed 42 · ümumi müddət 7.8 dəq

Bütün rəqəmlər `recsys train` tərəfindən real MovieLens 1M datası üzərində ölçülüb.

## Seçilmiş model

**hybrid** — qayda: highest validation ndcg@10 on warm users (tie-break: catalog coverage).

## Protokol

- Əsas split: **global_temporal** (80/10/10, zaman kəsiyi ilə). Modellər `train`-də öyrədilir, hiperparametrlər `val`-da seçilir, ən yaxşı konfiqurasiya `train+val` üzərində yenidən öyrədilib `test`-də **bir dəfə** qiymətləndirilir.
- Relevant: held-out reytinq ≥ 4.0. İstifadəçinin artıq gördüyü filmlər namizədlərdən çıxarılır.
- Əsas metrik: `ndcg@10`; 95% CI istifadəçilər üzrə bootstrap ilə (1000 nümunə).
- Task ölçüləri (istifadəçi sayı): `val_warm`=492, `test_warm`=1159, `secondary_test_warm`=5774, `cold_val_n0`=611, `cold_val_n1`=611, `cold_val_n3`=611, `cold_val_n5`=606, `cold_test_n0`=29, `cold_test_n1`=29, `cold_test_n3`=29, `cold_test_n5`=29

## Warm istifadəçilər — əsas cədvəl

| Model | Ailə | val ndcg@10 | test ndcg@10 (95% CI) | test P@10 | test Recall@20 | test MAP@10 | test HR@10 | coverage@10 | ILD@10 | novelty@10 |
|---|---|---|---|---|---|---|---|---|---|---|
| **hybrid** | hybrid | 0.1384 | 0.2347 [0.2194, 0.2503] | 0.2152 | 0.1066 | 0.1436 | 0.6704 | 0.058 | 0.789 | 1.53 |
| ials | collaborative | 0.1382 | 0.2267 [0.2119, 0.2415] | 0.2093 | 0.1031 | 0.1380 | 0.6540 | 0.061 | 0.785 | 1.56 |
| popularity | baseline | 0.1321 | 0.2071 [0.1940, 0.2201] | 0.1886 | 0.1067 | 0.1187 | 0.6618 | 0.032 | 0.765 | 1.59 |
| ease | collaborative | 0.1312 | 0.2192 [0.2049, 0.2344] | 0.1968 | 0.1059 | 0.1303 | 0.6549 | 0.099 | 0.779 | 1.76 |
| pure_svd | collaborative | 0.1291 | 0.2114 [0.1973, 0.2258] | 0.1925 | 0.0980 | 0.1262 | 0.6212 | 0.087 | 0.749 | 1.75 |
| user_knn | collaborative | 0.1284 | 0.2186 [0.2044, 0.2335] | 0.1975 | 0.0965 | 0.1325 | 0.6419 | 0.048 | 0.774 | 1.53 |
| item_knn | collaborative | 0.1272 | 0.2155 [0.2013, 0.2309] | 0.1951 | 0.0963 | 0.1306 | 0.6290 | 0.059 | 0.775 | 1.59 |
| content_tfidf | content | 0.0644 | 0.1302 [0.1205, 0.1406] | 0.1180 | 0.0559 | 0.0639 | 0.5246 | 0.340 | 0.725 | 3.99 |
| content_embedding | content | 0.0596 | 0.1042 [0.0953, 0.1128] | 0.0964 | 0.0479 | 0.0490 | 0.4737 | 0.291 | 0.667 | 3.73 |
| biased_mf | collaborative (explicit) | 0.0203 | 0.0433 [0.0386, 0.0485] | 0.0494 | 0.0382 | 0.0152 | 0.3037 | 0.078 | 0.697 | 7.75 |
| bias_baseline | baseline (explicit) | 0.0181 | 0.0437 [0.0396, 0.0484] | 0.0530 | 0.0309 | 0.0142 | 0.3322 | 0.010 | 0.823 | 4.98 |

## Cold-start (test dövründə yeni istifadəçilər)

`nX` = istifadəçinin ilk X real reytinqi tarixçə kimi verilir, qalanı proqnozlaşdırılır. `n0` yalnız populyarlıq / onboarding ilə xidmət oluna bilər.

| Model | cold_test_n0 ndcg@10 | cold_test_n1 ndcg@10 | cold_test_n3 ndcg@10 | cold_test_n5 ndcg@10 |
|---|---|---|---|---|
| hybrid | 0.4565 | 0.4455 | 0.4280 | 0.4452 |
| ials | 0.0264 | 0.3321 | 0.3769 | 0.4207 |
| popularity | 0.4565 | 0.4456 | 0.4316 | 0.4142 |
| ease | 0.0264 | 0.1856 | 0.2935 | 0.3585 |
| pure_svd | 0.0264 | 0.2840 | 0.3499 | 0.3965 |
| user_knn | 0.0264 | 0.3778 | 0.4159 | 0.4269 |
| item_knn | 0.0264 | 0.2403 | 0.3532 | 0.4028 |
| content_tfidf | 0.0264 | 0.0732 | 0.1386 | 0.1553 |
| content_embedding | 0.0264 | 0.0678 | 0.1165 | 0.1268 |
| biased_mf | 0.0523 | 0.0651 | 0.0635 | 0.0617 |
| bias_baseline | 0.0789 | 0.0789 | 0.0789 | 0.0734 |

### Yeni filmlər (train-də reytinqi olmayan, test-də relevant: 44)

| Model | new-item Recall@20 |
|---|---|
| hybrid | 0.0000 |
| ials | 0.0000 |
| popularity | 0.0000 |
| ease | 0.0000 |
| pure_svd | 0.0000 |
| user_knn | 0.0000 |
| item_knn | 0.0000 |
| content_tfidf | 0.0000 |
| content_embedding | 0.0000 |
| biased_mf | 0.0000 |
| bias_baseline | 0.0000 |

## Reytinq proqnozu (explicit modellər)

| Model | val RMSE | val MAE | test RMSE | test MAE | test RMSE (warm) |
|---|---|---|---|---|---|
| biased_mf | 0.9613 | 0.7712 | 0.8951 | 0.7014 | 0.8910 |
| bias_baseline | 0.9678 | 0.7694 | 0.9198 | 0.7205 | 0.9168 |

Qeyd: aşağı RMSE yaxşı top-N sıralaması demək deyil — explicit modellər 'nə qədər bəyənəcək' sualına, top-N modellər 'nəyi seçəcək' sualına cavab verir.

## Segmentlər (test, warm)

| Model | light ndcg@10 | heavy ndcg@10 | light istifadəçi | heavy istifadəçi |
|---|---|---|---|---|
| hybrid | 0.2708 | 0.2314 | 99 | 1060 |
| ials | 0.2580 | 0.2238 | 99 | 1060 |
| popularity | 0.2500 | 0.2031 | 99 | 1060 |
| ease | 0.2482 | 0.2165 | 99 | 1060 |
| pure_svd | 0.2381 | 0.2089 | 99 | 1060 |
| user_knn | 0.2598 | 0.2148 | 99 | 1060 |
| item_knn | 0.2439 | 0.2129 | 99 | 1060 |
| content_tfidf | 0.1331 | 0.1299 | 99 | 1060 |
| content_embedding | 0.1174 | 0.1030 | 99 | 1060 |
| biased_mf | 0.0734 | 0.0404 | 99 | 1060 |
| bias_baseline | 0.0604 | 0.0421 | 99 | 1060 |

## Robustness: per-user temporal split (seçimdə istifadə olunmur)

| Model | ndcg@10 | recall@20 |
|---|---|---|
| hybrid | 0.0736 | 0.1044 |
| ials | 0.0708 | 0.1026 |
| popularity | 0.0535 | 0.0830 |
| ease | 0.0845 | 0.1462 |
| pure_svd | 0.0688 | 0.1063 |
| user_knn | 0.0733 | 0.1136 |
| item_knn | 0.0756 | 0.1172 |
| content_tfidf | 0.0473 | 0.0776 |
| content_embedding | 0.0389 | 0.0681 |
| biased_mf | 0.0113 | 0.0307 |
| bias_baseline | 0.0097 | 0.0224 |

## Hybrid

Komponentlər: CF = `ials`, content = `content_tfidf`, popularity. Warm həddi: ≥ 5 reytinq.

| Bucket | w_cf | w_cb | w_pop |
|---|---|---|---|
| cold | 0.0 | 0.0 | 1.0 |
| light | 0.2 | 0.2 | 0.6 |
| warm | 0.8 | 0.1 | 0.1 |

Weights and components are chosen on validation, so the validation number is optimistic; the test split is the unbiased check.

## Ən yaxşı hiperparametrlər

Explicit modellər (bias_baseline, biased_mf) öz hədəfləri — validation RMSE ilə seçilir; qalanları validation `ndcg@10` ilə.

| Model | Parametrlər | Seçim meyarı | Grid ölçüsü |
|---|---|---|---|
| hybrid | `{"cf": "ials", "cb": "content_tfidf", "weights": {"cold": {"cf": 0.0, "cb": 0.0, "pop": 1.0}, "light": {"cf": 0.2, "cb": 0.2, "pop": 0.6}, "warm": {"cf": 0.8, "cb": 0.1, "pop": 0.1}}, "warm_min_history": 5}` | — | — |
| ials | `{"factors": 32, "reg": 200.0, "alpha": 2.0, "iterations": 15}` | val ndcg@10 | 24 |
| popularity | `{"half_life_events": 25000}` | val ndcg@10 | 7 |
| ease | `{"lambda_": 16000}` | val ndcg@10 | 6 |
| pure_svd | `{"factors": 4}` | val ndcg@10 | 5 |
| user_knn | `{"k": 1600}` | val ndcg@10 | 5 |
| item_knn | `{"k": 400, "shrink": 1000}` | val ndcg@10 | 12 |
| content_tfidf | `{"k": 25, "weighting": "centered"}` | val ndcg@10 | 8 |
| content_embedding | `{"k": 400, "weighting": "centered"}` | val ndcg@10 | 8 |
| biased_mf | `{"factors": 64, "reg": 0.1, "iterations": 12}` | val_rmse | 9 |
| bias_baseline | `{"reg_item": 2, "reg_user": 10}` | val_rmse | 12 |

## Limitlər

- MovieLens 1M 2000–2003-cü illərin datasıdır; müasir zövqləri və kataloqu əks etdirmir.
- Reytinqlər explicit-dir (1–5 ulduz). Top-N modellərdə hər reytinq 'qarşılıqlı əlaqə' kimi götürülür; bu, real implicit feedback (baxış, klik) ilə eyni deyil.
- Relevant = test reytinqi ≥ 4. İstifadəçinin görmədiyi, amma bəyənəcəyi filmlər 'səhv' sayılır, ona görə mütləq metrik dəyərləri aşağı qiymətləndirilir (offline qiymətləndirmənin ümumi problemi).
- Qlobal temporal split realistikdir, amma validation dövründə istifadəçilərin yarıdan çoxu yenidir (test dövründə isə yeni istifadəçi azdır); warm test dəsti aktiv, uzunmüddətli istifadəçilərə doğru meyllidir.
- Tag-lər və IMDb/TMDB id-ləri ML-32M-dən gəlir (2005–2023, fərqli istifadəçi populyasiyası). Bu, sonradan yaranmış item metadatasıdır; bəzi tag-lər (məs. 'imdb top 250') populyarlıq siqnalı daşıyır.
- Hybrid çəkiləri və komponentləri validation-da seçildiyi üçün hybrid-in validation nəticəsi optimistdir; qərəzsiz müqayisə test sütunlarıdır.
- Per-user temporal (ikinci) protokolda digər istifadəçilərin gələcək reytinqləri train-ə düşür; nəticələr yalnız robustness üçün göstərilir, model seçimində istifadə olunmur.
- Demoqrafik sahələr (yaş, cins, peşə) modellərdə istifadə edilmir.
- Offline metriklər onlayn keyfiyyətin (A/B test) əvəzi deyil.
