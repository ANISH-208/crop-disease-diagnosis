# Crop Doctor AI

Crop Doctor AI is a mobile-first crop leaf screening application. A farmer can take a photo or choose a JPG/PNG, review it, then send it to a FastAPI service that runs the trained EfficientNetV2-S classifier through LiteRT. The app returns crop guidance, stores browser-scoped reports, and routes uncertain cases for expert review.

The application is a portfolio and research prototype. It is not a substitute for local agronomic expertise or laboratory diagnosis.

## Features

- Camera-first photo check and gallery upload across 38 PlantVillage classes
- Farmer-readable results, symptoms, severity, and backend-provided next steps
- Browser-scoped reports from actual diagnosis responses
- Expert queue with pending, in-review, and resolved states
- Analytics, crop reference, model card, and settings screens
- SQLite alert and report storage locally; WebSockets are used in local development
- Upload validation, configurable limits, and model readiness reporting
- Installable PWA shell with a static offline fallback; diagnosis still requires internet

## Architecture

```text
React + Vite / PWA ── REST ── FastAPI
                  └── WebSocket (local development)
                                      ├── EfficientNetV2-S LiteRT (.tflite / Git LFS)
                                      ├── Disease metadata (38 classes)
                                      └── SQLite alerts and browser-scoped reports
```

The model accepts 224 × 224 RGB images and returns a softmax score for each of 38 classes. The backend scales scores to percentages and adds static metadata from `backend/disease_data.py`. Cases are escalated when the disease metadata requests expert review or the top score is below the configured confidence threshold.

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

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). The model loads lazily on the first diagnosis request; `/health` reports whether the model file is available.

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
| `CROP_DOCTOR_CONFIDENCE_THRESHOLD` | `80` | Below this score, request expert review |
| `CROP_DOCTOR_UPLOAD_DIR` | `backend/uploads` | Persisted images linked to alerts |
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
| `GET` | `/health` | API, model artifact, and database status |
| `GET` | `/diseases` | Supported model classes and field guidance |
| `POST` | `/diagnose` | Diagnose a multipart `file` upload |
| `GET` | `/reports` | List diagnoses for the `X-Report-Key` browser key |
| `GET` | `/alerts` | List alerts; optional `status` filter |
| `GET` | `/alerts/{alert_id}` | Get one alert |
| `PATCH` | `/alerts/{alert_id}` | Update alert status |
| WebSocket | `/ws` | Receive normalized realtime events |

Example diagnosis request (the browser sends its random `X-Report-Key` automatically):

```bash
curl -X POST http://127.0.0.1:8000/diagnose \
  -F 'file=@leaf.jpg;type=image/jpeg'
```

Example status update:

```bash
curl -X PATCH http://127.0.0.1:8000/alerts/ALERT_ID \
  -H 'Content-Type: application/json' \
  -d '{"status":"in_review"}'
```

WebSocket events use `{ "type": "alert_created", "data": { ... } }`. Current event types include `connection`, `diagnosis_started`, `diagnosis_completed`, `diagnosis_failed`, `alert_created`, and `alert_updated`.

## Development and checks

```bash
# Frontend checks
cd frontend
npm run lint
npm run build

# Backend regression checks, from the repository root
source .venv/bin/activate
python -m unittest discover -s tests -v

# Python syntax check
python -m compileall -q backend tests
```

The backend suite exercises API contracts, alert/report persistence and status transitions, upload validation and limits, disease metadata coverage, and a real held-out PlantVillage inference when the dataset is installed locally.

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

- Raw PlantVillage images, the generated manifest, uploads, SQLite databases, virtual environments, build output, and checkpoints are local/generated data and are ignored by Git.
- The model is trained on a controlled image dataset and may be unreliable on field imagery or unsupported conditions.
- Confidence is a model score, not a calibrated probability of disease.
- The application has no login system. Reports are scoped by a random key stored in that browser, not by a verified farmer identity; clearing site storage loses access to them.
- Vercel's SQLite and uploaded files use ephemeral `/tmp` storage and are not durable across cold starts. Use a persistent database and define photo retention before a real pilot.
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
