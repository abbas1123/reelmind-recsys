# Problemlərin həlli

## `SSL: CERTIFICATE_VERIFY_FAILED` (yükləmə zamanı)

Korporativ şəbəkə TLS trafikini öz sertifikatı ilə yenidən imzalayır və bu sertifikat Python-un `certifi` siyahısında yoxdur. Layihə `truststore` ilə əməliyyat sisteminin sertifikat anbarını istifadə edir (yoxlama söndürülmür). Xəta davam edərsə:

- Brauzerdə `https://files.grouplens.org/datasets/movielens/` açılırmı, yoxlayın.
- Alternativ: `ml-1m.zip` və `ml-32m.zip` fayllarını əl ilə yükləyib `data/raw/` qovluğuna qoyun, sonra `uv run recsys download` (MD5 yoxlanılır, yenidən yüklənmir).

## Embedding modeli yüklənmir

`uv run recsys download-models` Hugging Face-dən `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) yükləyir. Uğursuz olarsa sistem işləməyə davam edir: `content_embedding` və semantik axtarış söndürülür, TF-IDF content modeli qalır. Hesabatda bu, "skipped" kimi görünür.

## API `503 Recommendation engine not loaded`

Artifaktlar yoxdur. Ardıcıllıq: `uv run recsys preprocess` → `uv run recsys train` (və ya hamısı: `uv run recsys pipeline`). `GET /api/health` səbəbi `detail` sahəsində göstərir.

## `failed to remove file ... recsys.exe: The process cannot access the file`

`uv sync` işləyən `recsys` prosesinin exe faylını əvəz etməyə çalışır. Serveri/training-i dayandırın və ya `uv run --no-sync ...` istifadə edin.

## Training yavaşdır

- iALS və BiasedMF çoxlu kiçik xətti sistem həll edir. Kod BLAS-ı bu döngülərdə 1 thread-ə məhdudlaşdırır (`threadpoolctl`); bu olmadan thread-lər bir-birinə mane olur və fit 5–10 dəfə yavaşlayır.
- Tez yoxlama üçün: `uv run recsys train --quick` (hər modeldən 1 konfiqurasiya, ~5 dəq). Hesabatda "QUICK MODE" yazılır və integration testi bunu qəbul etmir.
- Yalnız bəzi modellər: `uv run recsys train --only ease --only content_tfidf`.

## GPU (opsional)

CPU kifayətdir: 3883 filmin embedding-i ~17 s çəkir. GPU istəsəniz:

```powershell
cd backend
uv sync --extra gpu        # torch CUDA 12.8 (RTX 50xx / Blackwell üçün lazımdır)
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_arch_list())"
```

`configs/default.yaml` → `embeddings.device: auto` CUDA-nı avtomatik seçir. Qeyd: `embeddings` və `gpu` extras birlikdə quraşdırıla bilməz (fərqli torch build-ləri). GPU yolu bu layihədə **sınaqdan keçirilməyib** (bax README, test statusu).

## Playwright brauzer tapmır

Konfiqurasiya sistemdəki Microsoft Edge-i istifadə edir (`channel: msedge`). Başqa brauzer üçün:

```powershell
$env:PW_CHANNEL = "chrome"; npm run test:e2e
# və ya Playwright-ın öz Chromium-u:
npx playwright install chromium; $env:PW_CHANNEL = "chromium"; npm run test:e2e
```

## Port məşğuldur

Backend 8010, frontend 5173 portunu istifadə edir (`strictPort`). Başqa port: `uv run recsys serve --port 8020` və `$env:VITE_API_PROXY = "http://127.0.0.1:8020"; npm run dev` (PowerShell).

## Datanı sıfırdan qurmaq

```powershell
Remove-Item -Recurse data\processed, artifacts\models, artifacts\embeddings
cd backend; uv run recsys pipeline --skip-download
```

`data/app.db` istifadəçi profillərini saxlayır; silsəniz profillər itir (kataloq avtomatik yenidən yüklənir).
