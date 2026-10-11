"""FastAPI application for crop diagnosis and expert alerts."""

import asyncio
import hmac
import logging
import uuid
import warnings
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from fastapi.exceptions import RequestValidationError

from backend import model
from backend.alerts import create_alert, get_alert, get_alerts, get_connection, get_reports, link_report_to_alert, save_report, update_alert_status
from backend.config import ALLOWED_ORIGINS, CONFIDENCE_THRESHOLD, DATABASE_PATH, EXPERT_API_KEY, MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES, REALTIME_AVAILABLE, UPLOAD_DIR
from backend.diagnosis import diagnose_image, disease_policy_status
from backend.disease_data import DISEASE_DATA
from backend.suitability import validator as suitability_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/jpg"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    status = model.model_status()
    logger.info("Crop Doctor API started model_status=%s model_version=%s", status["status"], status["version"])
    yield
    logger.info("Crop Doctor API stopped")


app = FastAPI(
    title="Crop Disease Diagnosis API",
    description="AI-assisted crop disease diagnosis and expert alert workflow.",
    version="3.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "X-Report-Key", "X-Expert-Key"],
)


class EventHub:
    """Owns connected WebSockets and publishes one normalized event contract."""

    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        logger.info("WebSocket connected active_connections=%s", len(self.connections))
        await self.send(websocket, "connection", {"status": "connected"}, str(uuid.uuid4()))

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)
        logger.info("WebSocket disconnected active_connections=%s", len(self.connections))

    async def send(self, websocket: WebSocket, event_type: str, data: dict, event_id: str) -> None:
        try:
            await websocket.send_json({"type": event_type, "event_id": event_id, "data": data})
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, event_type: str, data: dict) -> None:
        if not self.connections:
            return
        connections = tuple(self.connections)
        event_id = str(uuid.uuid4())
        outcomes = await asyncio.gather(
            *(self.send(websocket, event_type, data, event_id) for websocket in connections),
            return_exceptions=True,
        )
        for websocket, outcome in zip(connections, outcomes):
            if isinstance(outcome, Exception):
                self.disconnect(websocket)


events = EventHub()


class AlertStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "in_review", "resolved"]


class DiagnosisResponse(BaseModel):
    job_id: str
    created_at: str | None = None
    message: str
    crop: str | None = None
    diagnosis: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    severity: str | None = None
    symptoms: str | None = None
    prevention: list[str]
    expert_review: bool
    alert_created: bool = False
    alert: dict | None = None
    status: Literal["possible_disease_detected", "healthy_class_predicted", "uncertain"]
    model_version: str | None = None
    top_predictions: list[dict] = Field(default_factory=list)
    validation: dict | None = None


def require_expert_access(expert_key: str | None = Header(default=None, alias="X-Expert-Key")) -> None:
    """Protect the shared expert queue with a server-side bearer key."""
    if len(EXPERT_API_KEY) < 32:
        raise HTTPException(status_code=503, detail="Expert access is not configured with a key of at least 32 characters.")
    if not expert_key or not hmac.compare_digest(expert_key.encode("utf-8"), EXPERT_API_KEY.encode("utf-8")):
        raise HTTPException(status_code=401, detail="A valid expert access key is required.")


async def _save_and_validate_image(upload: UploadFile) -> Path:
    media_type = (upload.content_type or "").lower()
    original_filename = Path(upload.filename or "uploaded_image.jpg").name
    extension = Path(original_filename).suffix.lower()
    if media_type not in ALLOWED_IMAGE_TYPES or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Upload a JPG or PNG image.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_filename = f"{uuid.uuid4()}{extension}"
    file_path = UPLOAD_DIR / unique_filename
    size = 0
    try:
        with file_path.open("wb") as destination:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"Image must be smaller than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
                destination.write(chunk)
        if size == 0:
            raise HTTPException(status_code=400, detail="The uploaded image is empty.")

        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(file_path) as image:
                if image.format not in ALLOWED_IMAGE_FORMATS:
                    raise HTTPException(status_code=400, detail="The file contents are not a supported JPG or PNG image.")
                expected_format = "PNG" if extension == ".png" else "JPEG"
                if image.format != expected_format:
                    raise HTTPException(status_code=400, detail="The image contents do not match the file type.")
                width, height = image.size
                if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                    raise HTTPException(status_code=400, detail="Image dimensions exceed the supported limit.")
                image.verify()
            # Force pixel decoding as part of validation, then check EXIF-aware
            # dimensions and normalize transparency/grayscale consistently.
            from backend.image_utils import load_normalized_rgb

            normalized = load_normalized_rgb(file_path)
            if normalized.width * normalized.height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=400, detail="Image dimensions exceed the supported limit.")
            normalized.close()
        return file_path
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded image could not be decoded. Choose a valid JPG or PNG.") from exc
    except Exception:
        file_path.unlink(missing_ok=True)
        raise


@app.exception_handler(HTTPException)
async def http_error_handler(_request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "status" in exc.detail and "message" in exc.detail:
        content = exc.detail
    else:
        status = "invalid_image" if exc.status_code in {400, 413} else "not_found" if exc.status_code == 404 else "request_error"
        content = {"status": status, "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_request, exc: RequestValidationError):
    errors = exc.errors()
    missing_file = any(error.get("loc", ())[-1:] == ("file",) and error.get("type") == "missing" for error in errors)
    return JSONResponse(
        status_code=422,
        content={
            "status": "invalid_image" if missing_file else "invalid_request",
            "message": "Choose a JPG or PNG photo to continue." if missing_file else "The request could not be read. Check the photo and try again.",
        },
    )


@app.exception_handler(Exception)
async def unexpected_error_handler(_request, exc: Exception):
    logger.exception("Unhandled API exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred. Please retry."})


@app.get("/")
def home():
    return {"message": "FieldLeaf AI API is running.", "version": app.version, "realtime": REALTIME_AVAILABLE}


@app.get("/health")
def health():
    model_state = model.model_status()
    suitability_state = suitability_validator.status()
    disease_policy = disease_policy_status()
    try:
        connection = get_connection()
        try:
            connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
        database_state = "healthy"
    except Exception:
        logger.exception("Database health check failed")
        database_state = "unavailable"
    diagnosis_ready = model_state["ready"] and suitability_state["ready"] and disease_policy["ready"]
    healthy = diagnosis_ready and database_state == "healthy"
    return {
        "status": "healthy" if healthy else "degraded",
        "diagnosis_ready": diagnosis_ready,
        "realtime": REALTIME_AVAILABLE,
        "connections": len(events.connections),
        "model": model_state,
        "suitability": suitability_state,
        "disease_policy": disease_policy,
        "database": database_state,
        "database_persistence": "ephemeral" if str(DATABASE_PATH).startswith("/tmp/") else "local",
    }


@app.get("/diseases")
def diseases():
    classes = [
        {
            "class": class_name,
            "crop": DISEASE_DATA[class_name]["crop"],
            "diagnosis": DISEASE_DATA[class_name]["disease"],
            "severity": DISEASE_DATA[class_name]["severity"],
            "symptoms": DISEASE_DATA[class_name]["symptoms"],
            "prevention": DISEASE_DATA[class_name]["prevention"],
            "expert_review": DISEASE_DATA[class_name]["expert_review"],
        }
        for class_name in model.CLASS_NAMES
    ]
    return {"count": len(classes), "classes": classes}


@app.websocket("/ws")
async def realtime_socket(websocket: WebSocket):
    await events.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        events.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket receive failed")
        events.disconnect(websocket)


@app.post("/diagnose", response_model=DiagnosisResponse)
async def diagnose(
    file: UploadFile = File(...),
    report_key: str | None = Header(default=None, min_length=32, alias="X-Report-Key"),
):
    try:
        if report_key is not None and len(report_key) < 32:
            raise HTTPException(status_code=422, detail="X-Report-Key must contain at least 32 characters.")
        file_path = await _save_and_validate_image(file)
    finally:
        await file.close()

    job_id = str(uuid.uuid4())
    try:
        await events.broadcast("diagnosis_started", {"job_id": job_id, "status": "started"})
        logger.info("Photo check started job_id=%s", job_id)
        validation = await asyncio.to_thread(suitability_validator.validate_image, str(file_path))
        if validation.get("status") == "unavailable":
            await events.broadcast("diagnosis_failed", {"job_id": job_id, "status": "validation_unavailable"})
            raise HTTPException(status_code=503, detail={
                "status": "validation_unavailable",
                "message": validation.get("message", "The crop photo check is not available yet."),
            })
        if validation.get("status") == "not_plant":
            await events.broadcast("diagnosis_completed", {"job_id": job_id, "status": "not_plant"})
            raise HTTPException(status_code=422, detail={
                "status": "not_plant",
                "message": "This photo does not look like a crop or leaf photo. Choose a clear crop photo and try again.",
                "validation": {key: value for key, value in validation.items() if key != "message"},
            })
        if validation.get("status") != "suitable":
            await events.broadcast("diagnosis_failed", {"job_id": job_id, "status": "uncertain"})
            raise HTTPException(status_code=503, detail={
                "status": "validation_unavailable",
                "message": "The crop photo check could not verify this image. Please try another photo.",
            })

        diagnosis = await asyncio.to_thread(diagnose_image, str(file_path), validation)
        response = {
            "job_id": job_id,
            **diagnosis,
            "expert_review": bool(diagnosis.get("expert_review")),
            "alert_created": False,
            "alert": None,
            "validation": {key: value for key, value in validation.items() if key != "message"},
        }
        if diagnosis["status"] != "uncertain":
            confidence = float(diagnosis["confidence"])
            needs_expert_review = bool(diagnosis.get("expert_review")) or confidence < CONFIDENCE_THRESHOLD
            response["expert_review"] = needs_expert_review
            if report_key:
                stored_report = await asyncio.to_thread(save_report, response, report_key)
                response["created_at"] = stored_report["created_at"]
            if needs_expert_review:
                alert = await asyncio.to_thread(
                    create_alert,
                    crop=diagnosis["crop"],
                    diagnosis=diagnosis["diagnosis"],
                    severity=diagnosis["severity"],
                    confidence=confidence,
                    symptoms=diagnosis.get("symptoms") or "",
                    image_filename=None,
                    validation_model_version=validation.get("model_version"),
                )
                response["alert"] = alert
                response["alert_created"] = True
                if report_key:
                    await asyncio.to_thread(link_report_to_alert, job_id, alert["id"])

        await events.broadcast("diagnosis_completed", {"job_id": job_id, "status": diagnosis["status"]})
        if response["alert"]:
            await events.broadcast("alert_created", {"alert": response["alert"]})
            logger.info("Expert alert created job_id=%s alert_id=%s", job_id, response["alert"]["id"])
        logger.info("Photo check completed job_id=%s status=%s", job_id, diagnosis["status"])
        return response
    except Exception as exc:
        if not isinstance(exc, HTTPException):
            logger.exception("Photo check failed job_id=%s", job_id)
            await events.broadcast("diagnosis_failed", {"job_id": job_id, "status": "failed"})
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=503, detail={
            "status": "service_unavailable",
            "message": "The crop photo check is temporarily unavailable. Please try again.",
        }) from exc
    finally:
        # Uploaded photos are only used for this request and are never retained.
        file_path.unlink(missing_ok=True)


@app.get("/alerts")
def alerts(
    status: Literal["pending", "in_review", "resolved"] | None = Query(default=None),
    _expert_access: None = Depends(require_expert_access),
):
    current = get_alerts(status)
    return {"count": len(current), "alerts": current}


@app.get("/reports")
def reports(
    report_key: str = Header(..., min_length=32, alias="X-Report-Key"),
    limit: int = Query(default=50, ge=1, le=100),
):
    current = get_reports(report_key, limit)
    return {"count": len(current), "reports": current}


@app.get("/alerts/{alert_id}")
def single_alert(alert_id: str, _expert_access: None = Depends(require_expert_access)):
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


@app.patch("/alerts/{alert_id}")
async def change_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
    _expert_access: None = Depends(require_expert_access),
):
    alert = update_alert_status(alert_id, update.status)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    await events.broadcast("alert_updated", {"alert": alert})
    logger.info("Alert updated alert_id=%s status=%s", alert_id, update.status)
    return {"message": "Alert status updated successfully", "alert": alert}
