# Qiymətləndirmə metodologiyası və nəticələr

Mənbə: `artifacts/reports/model_comparison.json` (maşın oxuyur) və `model_comparison.md` (insan oxuyur). Aşağıdakı rəqəmlər son tam `recsys train` işindən götürülüb (seed 42, CPU, 7.8 dəq). Yenidən işlətdikdə eyni seed ilə eyni nəticələr alınır (`tests/integration/test_real_pipeline.py::test_reported_test_metric_is_reproducible`).

## Protokol

1. **Split:** qlobal temporal 80/10/10 (bax [DATASET.md](DATASET.md)). Leakage avtomatik yoxlanır.
2. **Tuning:** hər model `train` üzərində öyrədilir, hər grid konfiqurasiyası `val` üzərində qiymətləndirilir. Seçim meyarı: `val ndcg@10` (explicit modellər üçün `val RMSE`).
3. **Test:** ən yaxşı konfiqurasiya `train+val` üzərində yenidən öyrədilir və `test`-də **bir dəfə** qiymətləndirilir. Test nəticələri heç bir qərarda istifadə olunmur.
4. **Relevant:** held-out reytinq ≥ 4. İstifadəçinin artıq qiymətləndirdiyi filmlər namizədlərdən çıxarılır.
5. **Warm task:** train hissəsində tarixçəsi və held-out hissədə ≥1 relevant filmi olan istifadəçilər (val: 492, test: 1 159).
6. **Cold task:** train-də tarixçəsi olmayan istifadəçilər. İlk *n* ∈ {0, 1, 3, 5} real reytinqi (zaman sırası ilə) tarixçə kimi verilir, qalanı hədəfdir (val: 611, test: 29 istifadəçi).
7. **Robustness:** istifadəçi daxili temporal split üzrə eyni konfiqurasiyalar (seçimdə istifadə olunmur).
8. **Serving:** seçilmiş konfiqurasiya bütün data (train+val+test) üzərində öyrədilib saxlanılır.

Grid-lər iki dəfə genişləndirilib: ən yaxşı validation dəyəri grid kənarına düşəndə. Bu qərarlar yalnız validation-a əsaslanır.

## Metriklər

| Metrik | Mənası |
|---|---|
| Precision@K | top-K-nın neçə faizi relevantdır |
| Recall@K | relevant filmlərin neçə faizi top-K-dadır |
| NDCG@K | yuxarı sıralardakı hit-lər daha çox çəki alır (əsas metrik) |
| MAP@K | hər hit-dəki precision-ın ortalaması |
| HitRate@K | ən azı bir hit olan istifadəçilərin payı |
| MRR@K | ilk hit-in sırasının tərsi |
| RMSE / MAE | explicit reytinq proqnozunun xətası |
| Coverage@10 | kataloqun neçə faizi kiminsə top-10-unda görünür |
| ILD@10 | siyahı daxilində janr müxtəlifliyi (Jaccard məsafəsi) |
| Novelty@10 | tövsiyələrin orta "təəccüb" dərəcəsi, −log₂(populyarlıq payı) |
| Gini@10 | tövsiyə ekspozisiyasının konsentrasiyası |

Metriklərin vektorlaşdırılmış versiyaları sadə Python reference implementasiyalarına və əllə hesablanmış nümunəyə qarşı test olunur (`tests/unit/test_metrics.py`). NDCG@10 üçün 95% CI istifadəçilər üzrə 1000 bootstrap nümunəsi ilə hesablanır.

## Modellər və ən yaxşı hiperparametrlər

| Model | Ailə | Ən yaxşı parametrlər | Seçim meyarı |
|---|---|---|---|
| popularity | baseline | `half_life_events=25000` (trending) | val ndcg@10 |
| bias_baseline | baseline (explicit) | `reg_item=2, reg_user=10` | val RMSE |
| user_knn | CF | `k=1600` | val ndcg@10 |
| item_knn | CF | `k=400, shrink=1000` | val ndcg@10 |
| pure_svd | CF | `factors=4` | val ndcg@10 |
| ials | CF | `factors=32, reg=200, alpha=2, iterations=15` | val ndcg@10 |
| ease | CF | `lambda_=16000` | val ndcg@10 |
| biased_mf | CF (explicit) | `factors=64, reg=0.1, iterations=12` | val RMSE |
| content_tfidf | content | `k=25, weighting=centered` | val ndcg@10 |
| content_embedding | content | `k=400, weighting=centered` | val ndcg@10 |
| hybrid | hybrid | CF=`ials`, content=`content_tfidf`, çəkilər aşağıda | val ndcg@10 |

Qeyd: `item_knn shrink=1000` və `bias_baseline reg_item=2` hələ də grid kənarındadır. Bu iki model seçilməyib; grid-i daha da genişləndirmək onların nəticəsini bir qədər dəyişə bilər.

**Müşahidə:** temporal split güclü regulyarizasiyanı mükafatlandırır (EASE λ=16000, iALS reg=200, PureSVD 4 faktor). Gələcək dövrdə istifadəçilər çox vaxt populyar yeni filmləri izləyir, ona görə "populyarlığa yaxın" modellər üstünlük qazanır.

### Hybrid çəkiləri

| Bucket | Tarixçə | w_cf (iALS) | w_cb (TF-IDF) | w_pop (trending) |
|---|---|---|---|---|
| cold | 0 | 0.0 | 0.0 | 1.0 |
| light | 1–4 | 0.2 | 0.2 | 0.6 |
| warm | ≥ 5 | 0.8 | 0.1 | 0.1 |

## Nəticələr — warm istifadəçilər (test, 1 159 istifadəçi)

| Model | val NDCG@10 | test NDCG@10 [95% CI] | test Recall@20 | Coverage@10 |
|---|---|---|---|---|
| **hybrid** (seçilib) | 0.1384 | **0.2347** [0.219, 0.250] | 0.1066 | 0.058 |
| ials | 0.1382 | 0.2267 [0.212, 0.241] | 0.1031 | 0.061 |
| popularity | 0.1321 | 0.2071 [0.194, 0.220] | 0.1067 | 0.032 |
| ease | 0.1312 | 0.2192 [0.205, 0.234] | 0.1059 | 0.099 |
| pure_svd | 0.1291 | 0.2114 [0.197, 0.226] | 0.0980 | 0.087 |
| user_knn | 0.1284 | 0.2186 [0.204, 0.234] | 0.0965 | 0.048 |
| item_knn | 0.1272 | 0.2155 [0.201, 0.231] | 0.0963 | 0.059 |
| content_tfidf | 0.0644 | 0.1302 [0.121, 0.141] | 0.0559 | 0.340 |
| content_embedding | 0.0596 | 0.1042 [0.095, 0.113] | 0.0479 | 0.291 |
| biased_mf | 0.0203 | 0.0433 [0.039, 0.048] | 0.0382 | 0.078 |
| bias_baseline | 0.0181 | 0.0437 [0.040, 0.048] | 0.0309 | 0.010 |

Şərh:

- Hybrid test-də ən yüksək NDCG@10-a malikdir: iALS-dən +3.5%, popularity-dən +13.3%. Hybrid ilə iALS-in CI-ları üst-üstə düşür — fərq kiçikdir və bu test dəstində statistik baxımdan qəti deyil.
- Validation-da hybrid ilə iALS demək olar bərabərdir (0.1384 vs 0.1382). Hybrid-in çəkiləri validation-da seçildiyi üçün onun validation nəticəsi optimistdir.
- Trending popularity çox güclü baseline-dır. Bu, temporal qiymətləndirmənin tipik nəticəsidir və dərsdə vurğulanmalıdır.
- Content modelləri dəqiqlikdə zəifdir, amma ən yüksək coverage-ə malikdir (kataloqun 29–34%-i). Onların hybrid-dəki rolu yeni/az tanınan filmləri əlçatan etməkdir.
- Explicit modellər RMSE-də yaxşıdır (BiasedMF test RMSE 0.8951, bias baseline 0.9198), amma top-N sıralamada ən zəifdir: "nə qədər bəyənəcək" ilə "nəyi seçəcək" fərqli suallardır.

## Cold-start (NDCG@10)

| Model | test n0 | test n1 | test n3 | test n5 | val n0 | val n1 | val n3 | val n5 |
|---|---|---|---|---|---|---|---|---|
| hybrid | 0.4565 | 0.4455 | 0.4280 | 0.4452 | 0.3516 | 0.3576 | 0.3528 | 0.3545 |
| popularity | 0.4565 | 0.4456 | 0.4316 | 0.4142 | 0.3516 | 0.3460 | 0.3390 | 0.3319 |
| user_knn | 0.0264 | 0.3778 | 0.4159 | 0.4269 | 0.0175 | 0.3334 | 0.3516 | 0.3484 |
| ials | 0.0264 | 0.3321 | 0.3769 | 0.4207 | 0.0175 | 0.2952 | 0.3403 | 0.3491 |

- `n0`-da yalnız populyarlıq işləyir; CF modelləri boş tarixçə ilə təsadüfi nəticə verir (0.02).
- Validation-da (611 istifadəçi) hybrid bütün *n* üçün popularity-dən yaxşıdır. Test-də cəmi 29 yeni istifadəçi var, fərqlər səs-küylüdür.
- Onboarding janrları ilə zənginləşdirmə (cold bucket-də janr affinity, MMR) data ilə tənzimlənməyib: held-out "seçilmiş janrlar" siqnalı yoxdur. Bu, sənədləşdirilmiş heuristic-dir.

## Yeni filmlər

Test dövründə ilk dəfə görünən filmlər üzrə relevant hədəflər çox azdır (44). Heç bir model onları top-20-də tapmayıb (new-item Recall@20 = 0). Content modelləri bu filmləri **skorlaya** bilir (onlar üçün CF skoru 0-dır), amma tanınmış filmlərlə rəqabətdə yuxarı qalxmırlar. UI-da reytinqsiz 177 film "Same vibe" (content) oxşarlığı ilə əlçatandır.

## Robustness: per-user temporal split (NDCG@10, 5 774 istifadəçi)

| ease | hybrid | item_knn | user_knn | ials | pure_svd | popularity | content_tfidf | content_embedding | biased_mf | bias_baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0845 | 0.0736 | 0.0756 | 0.0733 | 0.0708 | 0.0688 | 0.0535 | 0.0473 | 0.0389 | 0.0113 | 0.0097 |

Bu protokolda sıralama dəyişir: EASE birincidir, hybrid geridə qalır. Səbəb: hybrid-in çəkiləri və trending komponenti qlobal temporal ssenari üçün tənzimlənib; per-user split-də hər istifadəçinin "gələcəyi" müxtəlif tarixlərdədir və ümumi trend siqnalı az kömək edir. Bu, **qiymətləndirmə protokolunun model seçiminə təsirini** göstərən yaxşı dərs nümunəsidir. Əsas protokol real istifadəyə (keçmişdə öyrən, gələcəyi tövsiyə et) daha yaxın olduğu üçün seçim ona görə edilir.

## Limitlər

Tam siyahı hesabatın sonunda və dashboard-dadır (`LIMITATIONS` — `recsys/evaluation/report.py`). Əsasları: köhnə dataset (2000–2003), explicit reytinqlərin implicit kimi istifadəsi, kiçik test cold-start dəsti, sonrakı dövrə aid tag metadatası, offline metriklərin onlayn keyfiyyətə bərabər olmaması.
