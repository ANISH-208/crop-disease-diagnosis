# FieldLeaf AI

FieldLeaf AI is a mobile-first crop photo screening prototype. A farmer can take a photo or choose a JPG/PNG, review it, then send it to a FastAPI service. Before upload, the browser applies EXIF orientation and scales the image to at most 1024 pixels on its longest edge, keeping camera photos within the API's 4 MB request limit. The API validates image bytes, runs a separate crop/leaf suitability gate, and only then considers the trained EfficientNetV2-S disease classifier.

The application is a portfolio and research prototype. It is not a substitute for local agronomic expertise or laboratory diagnosis.

## Features

- Camera and gallery selection with client and server image validation
- Dark forest-green glass interface with high-contrast text and touch-friendly actions
- Farmer-readable results, symptoms, severity, and backend-provided next steps
- Browser-scoped reports from actual diagnosis responses
- Expert queue with pending, in-review, and resolved states
- Analytics, crop reference, model card, and settings screens
- SQLite alert and report storage locally; WebSockets are used in local development
- Fail-closed suitability validation and explicit uncertainty states
- Upload validation, configurable limits, and readiness reporting
- Installable PWA shell with a static offline fallback; diagnosis still requires internet

## Architecture

```text
React + Vite / PWA ── REST ── FastAPI
                  └── WebSocket (local development)
                                      ├── Crop/leaf validator LiteRT (.tflite + evaluated JSON metadata)
                                      ├── EfficientNetV2-S disease classifier LiteRT (.tflite)
                                      ├── Disease metadata (38 classes)
                                      └── SQLite alerts and browser-scoped reports
```

The existing disease model accepts 224 × 224 RGB images with 0–255 pixel values, matching the training script. The backend applies EXIF orientation, composites transparency onto white, converts grayscale/RGB formats to RGB, and bilinear-resizes before inference. Disease labels are held back unless a separate crop/leaf validator and both disease acceptance thresholds are configured.

### Suitability gate and current availability

There is no trained suitability model, negative image set, or evaluation report in this checkout. For safety, `/diagnose` does **not** call the 38-class disease classifier until `models/crop_suitability.tflite` and its evaluated `models/crop_suitability.json` sidecar are installed. The UI disables analysis while this gate is unavailable. A direct API request returns `503 validation_unavailable`; a validated negative returns `422 not_plant` before disease classification.

`ml_v6/scripts/train_suitability.py` implements a separate two-class training pipeline. It requires a user-supplied licensed image manifest with grouped `train`, `validation`, and `test` splits; it rejects group and exact-file leakage, requires positive examples across at least three crop/leaf categories, and requires negative examples for people, animals, vehicles, documents, buildings, natural objects, green confusers, and other negatives. The script selects its acceptance threshold on validation data under a user-specified maximum false-acceptance rate and writes test precision, recall, F1, confusion matrix, false-acceptance rate, and false-rejection rate to the sidecar. No training data or metrics are fabricated or bundled.

The disease classifier also remains in uncertain mode until calibrated `CROP_DOCTOR_DISEASE_MIN_PROBABILITY` and `CROP_DOCTOR_DISEASE_MIN_MARGIN` values are supplied. The existing 80% expert-review threshold is not treated as a diagnosis acceptance threshold.

### Benchmark context

The reported **99.04% accuracy**, **99.98% top-5 accuracy**, and **98.58% macro F1** are results on the held-out PlantVillage test set (5,545 images). They are **in-domain benchmark results**, not real-world field accuracy. Field images can differ in lighting, camera quality, crop variety, growth stage, and co-occurring symptoms.

## Requirements

- Python 3.13 (Vercel runtime) or newer supported by LiteRT
- Node.js 20.19+ (or 22.12+)
- Git LFS for the trained model artifact
- About 22 MB for the LiteRT model plus Python runtime dependencies

## Run locally

From the repository root:

```bash
git lfs install
git lfs pull
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). The model loads lazily. `/health` reports model, validator, calibrated disease policy, database, and diagnosis readiness. With this checkout as provided, photo selection and preview work, while analysis stays disabled because no suitability artifact or calibrated disease policy is present.

## Deploy on Vercel

The root `vercel.json` defines two services in one Vercel project: the FastAPI API at `/api/*` and the Vite frontend at `/`. Set the Vercel project's root directory to `.` and deploy the `main` branch. Vercel's Python runtime installs the lightweight dependencies from `requirements.txt`; the API uses the 22 MB LiteRT artifact. Production frontend builds always call the same-origin `/api` route, even if an old `VITE_API_URL` or `VITE_WS_URL` value remains in project settings. Vercel Functions do not provide persistent WebSocket connections, so production uses REST requests.

Vercel functions have an ephemeral filesystem. This demo uses `/tmp` for its SQLite database and uploaded files, so reports and expert alerts can be lost across cold starts. Each browser creates a random report key and sends it with diagnoses; only its hash is stored, so `/reports` returns only reports associated with that browser key. Clearing browser storage loses access to those reports. Configure a persistent database and object storage before relying on long-term case records.

The web app can be installed as a PWA on supported browsers. Its service worker caches only the static app shell and assets, never API responses or crop uploads. Offline mode can open cached screens, but image diagnosis needs an internet connection. A PWA is not a native Android or iOS app; store distribution still requires a native wrapper (such as Capacitor), signing, device testing, privacy disclosures, and store review.

### Environment variables

Backend variables are read from the process environment:

| Variable | Default | Purpose |
| --- | --- | --- |
| `CROP_DOCTOR_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated CORS origins |
| `CROP_DOCTOR_MAX_UPLOAD_BYTES` | `4194304` | Maximum image size (4 MiB; fits Vercel's function request limit) |
| `CROP_DOCTOR_MAX_IMAGE_PIXELS` | `40000000` | Maximum decoded image pixels |
| `CROP_DOCTOR_CONFIDENCE_THRESHOLD` | `80` | Below this result score, request expert review after the separate acceptance policy passes |
| `CROP_DOCTOR_DISEASE_MIN_PROBABILITY` | unset | Calibrated minimum top-class probability required for a disease result |
| `CROP_DOCTOR_DISEASE_MIN_MARGIN` | unset | Calibrated minimum gap between the top two disease classes |
| `CROP_DOCTOR_SUITABILITY_MODEL_PATH` | `models/crop_suitability.tflite` | Separate crop/leaf validator; requires a valid `.json` sidecar beside it |
| `CROP_DOCTOR_EXPERT_API_KEY` | unset | Shared bearer key required to read or update expert alerts; alert endpoints return `503` until configured |
| `CROP_DOCTOR_UPLOAD_DIR` | `backend/uploads` | Temporary request image directory; photos are deleted after each check |
| `CROP_DOCTOR_DATABASE_PATH` | `backend/alerts.db` | SQLite alert database |
| `CROP_DOCTOR_MODEL_PATH` | `models/crop_doctor_v6_efficientnetv2s.keras` | Optional Keras fallback model |
| `CROP_DOCTOR_LITE_MODEL_PATH` | `models/crop_doctor_v6_efficientnetv2s.tflite` | LiteRT inference model |

Frontend variables are configured in `frontend/.env`:

```dotenv
VITE_API_URL=http://127.0.0.1:8000
VITE_WS_URL=ws://127.0.0.1:8000/ws
```

In local development, `VITE_WS_URL` can point to the FastAPI WebSocket. Production ignores both variables and uses `/api` on the same Vercel origin; Vercel serverless functions do not keep persistent WebSocket connections.

## API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Service information |
| `GET` | `/health` | API, disease model, suitability validator, acceptance policy, database, and diagnosis readiness |
| `GET` | `/diseases` | Supported model classes and field guidance |
| `POST` | `/diagnose` | Validate a multipart `file`, then return a possible result, uncertainty, or structured error |
| `GET` | `/reports` | List diagnoses for the `X-Report-Key` browser key |
| `GET` | `/alerts` | List alerts; requires `X-Expert-Key`; optional `status` filter |
| `GET` | `/alerts/{alert_id}` | Get one alert; requires `X-Expert-Key` |
| `PATCH` | `/alerts/{alert_id}` | Update alert status; requires `X-Expert-Key` |
| WebSocket | `/ws` | Receive normalized realtime events |

Example diagnosis request (the browser sends its random `X-Report-Key` automatically):

```bash
curl -X POST http://127.0.0.1:8000/diagnose \
  -F 'file=@leaf.jpg;type=image/jpeg'
```

Example status update:

```bash
curl -X PATCH http://127.0.0.1:8000/alerts/ALERT_ID \
  -H 'X-Expert-Key: YOUR_CONFIGURED_EXPERT_KEY' \
  -H 'Content-Type: application/json' \
  -d '{"status":"in_review"}'
```

Diagnosis response statuses are `possible_disease_detected`, `healthy_class_predicted`, and `uncertain`. Structured error statuses include `invalid_image`, `not_plant`, `validation_unavailable`, and `service_unavailable`. Missing or unsupported images return HTTP `400`/`422`; oversized images return `413`; validated non-plant inputs return `422`; missing model/policy components return `503`. `no_leaf_detected` is not returned because the current validation architecture has no leaf detector.

Set `CROP_DOCTOR_EXPERT_API_KEY` to a random secret with at least 32 characters on the API server. Experts enter that same key in **Settings**; the browser keeps it in session storage for the current tab. The key is shared by the expert team and does not provide individual accounts or per-user audit identity. Do not put it in frontend build variables or commit it to the repository. WebSocket events use `{ "type": "alert_created", "event_id": "...", "data": { "alert": { ... } } }`; alert events include the matching alert ID and full alert payload. Current event types include `connection`, `diagnosis_started`, `diagnosis_completed`, `diagnosis_failed`, `alert_created`, and `alert_updated`. WebSockets are only enabled in local development; Vercel uses REST because serverless functions do not hold persistent socket connections.

## Development and checks

```bash
# Frontend checks
cd frontend
npm run lint
npm run test
npm run build

# Backend regression checks, from the repository root
source .venv/bin/activate
python -m unittest discover -s tests -v

# Python syntax check
python -m compileall -q backend tests
```

The frontend suite exercises camera/gallery actions, preview and retake, image validation, loading/error states, rejection/uncertainty/success rendering, mobile navigation, empty reports, structured API responses, and WebSocket disconnect cleanup. The backend suite exercises API contracts, structured errors, alert/report persistence, event IDs and matching alert payloads, upload validation, fail-closed suitability gating, and real held-out PlantVillage inference. It does not claim real negative-image rejection because no validator or representative negative test set is present.

Optional ML/training dependencies are listed separately:

```bash
python -m pip install -r requirements-ml.txt
python ml_v6/scripts/download_plantvillage.py
python ml_v6/scripts/build_manifest.py
python ml_v6/scripts/create_leaf_split.py
python ml_v6/scripts/validate_dataset.py
python ml_v6/scripts/train_v6.py
python ml_v6/scripts/sanity_check.py
```

Training is intentionally not part of the API install. `dataset_manifest.csv` is generated locally from the raw images and ignored by Git. The optional leaf-group map improves split isolation; without it, the split utility uses deterministic hash assignment and consolidates exact duplicate images. Training writes the production model to `models/crop_doctor_v6_efficientnetv2s.keras`; that artifact must remain managed by Git LFS.

To train the separate suitability model, first collect a licensed image set and build a CSV manifest with columns `image_path,label,group_id,split,category`. Labels are `not_plant` or `crop_or_leaf`; splits are `train`, `validation`, or `test`; `group_id` must identify all photos from one source plant/scene/capture group. Include the required negative categories described by the script and at least three positive crop/leaf categories. Verify the dataset license before training. Then run:

```bash
python ml_v6/scripts/train_suitability.py \
  --manifest /path/to/suitability_manifest.csv \
  --data-root /path/to/images \
  --output-dir models \
  --dataset-source 'Dataset citation or URL' \
  --dataset-license 'Verified license' \
  --max-validation-false-accept-rate 0.01
```

The example `0.01` is an operator-selected validation constraint, not a universal safe threshold; review the resulting held-out test metrics before deploying the artifact. The training command is intentionally not run here because this repository has no labeled negative set and no such license/evaluation can be verified.

Disease class acceptance thresholds can be selected separately from grouped PlantVillage validation data with `ml_v6/scripts/calibrate_disease_policy.py`. It chooses probability and top-two margin thresholds for a requested maximum validation selective error, reports held-out test coverage/error, and prints the two environment variables to review. Do not copy those values into production until the test trade-off is acceptable; PlantVillage performance still does not establish field reliability.

```bash
python ml_v6/scripts/calibrate_disease_policy.py \
  --manifest ml_v6/datasets/dataset_manifest.csv \
  --output ml_v6/outputs/disease_acceptance_policy.json \
  --max-selective-error-rate 0.01
```

To refresh the compact inference artifact after retraining, install the optional ML dependencies and run `python scripts/convert_lite_model.py`. The Vercel API project should use the repository root, with `index.py` as the FastAPI entrypoint. Its `/tmp` SQLite database is ephemeral; connect a persistent database before using expert alerts as durable records.

## Repository layout

```text
backend/          FastAPI routes, model inference, metadata, SQLite alerts
frontend/         React + Vite application
ml_v6/datasets/   Class taxonomy; raw images and generated manifest are local
ml_v6/scripts/    Dataset preparation, training, and evaluation utilities
ml_v6/outputs/    Tracked evaluation report and class mapping
models/           Production EfficientNetV2-S model (Git LFS)
tests/            Backend and model integration regressions
```

## Data and limitations

- Raw PlantVillage images, suitability images, generated manifests, temporary uploads, SQLite databases, virtual environments, build output, and checkpoints are local/generated data and are ignored by Git.
- No real suitability model, suitability dataset, or negative image evaluation is currently available. The analysis action remains disabled until a trained model with its validation sidecar is installed.
- The model is trained on a controlled image dataset and may be unreliable on field imagery or unsupported conditions.
- Confidence is a model score, not a guarantee or calibrated probability of disease.
- The application has no individual accounts. Reports are scoped by a random key stored in that browser, not by a verified farmer identity; clearing site storage loses access to them. Expert alerts are protected by one shared server-configured API key, not per-user identity.
- Vercel's SQLite uses ephemeral `/tmp` storage and is not durable across cold starts. Uploaded photos are deleted after processing. Use a persistent database before relying on long-term reports or expert alerts.
- The interface is localization-ready but only English copy is currently provided. Diagnosis labels and guidance come from the existing English dataset metadata.
- The PWA shell can be installed where supported, but native Android/iOS packaging and app-store submission have not been completed.

## Future improvements

- Calibrate confidence scores and evaluate on independently collected field images across lighting, devices, and crop varieties.
- Add authenticated expert accounts, role-based access, and an auditable record of review decisions.
- Define configurable image retention and deletion policies for production deployments.
- Add deployment observability for inference latency, model errors, and alert resolution time.

## Git LFS

The production model is tracked through `.gitattributes`:

```bash
git lfs ls-files
```

It should list `models/crop_doctor_v6_efficientnetv2s.keras`. Do not commit raw datasets, local environment files, databases, uploaded images, or generated model checkpoints.
