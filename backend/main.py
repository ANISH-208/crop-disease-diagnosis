"""FastAPI application for crop diagnosis and expert alerts."""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field

from backend import model
from backend.alerts import create_alert, get_alert, get_alerts, get_connection, get_reports, save_report, update_alert_status
from backend.config import ALLOWED_ORIGINS, CONFIDENCE_THRESHOLD, MAX_IMAGE_PIXELS, MAX_UPLOAD_BYTES, UPLOAD_DIR
from backend.diagnosis import diagnose_image
from backend.disease_data import DISEASE_DATA

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
    allow_headers=["Content-Type", "X-Report-Key"],
)


class EventHub:
    """Owns connected WebSockets and publishes one normalized event contract."""

    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        logger.info("WebSocket connected active_connections=%s", len(self.connections))
        await self.send(websocket, "connection", {"status": "connected"})

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)
        logger.info("WebSocket disconnected active_connections=%s", len(self.connections))

    async def send(self, websocket: WebSocket, event_type: str, data: dict) -> None:
        try:
            await websocket.send_json({"type": event_type, "data": data})
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, event_type: str, data: dict) -> None:
        if not self.connections:
            return
        connections = tuple(self.connections)
        outcomes = await asyncio.gather(
            *(self.send(websocket, event_type, data) for websocket in connections),
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
    filename: str
    original_filename: str
    crop: str
    diagnosis: str
    confidence: float = Field(ge=0, le=100)
    severity: str
    symptoms: str
    prevention: list[str]
    expert_review: bool
    alert_created: bool
    alert: dict | None
    status: Literal["diagnosed"]
    model_version: str
    top_predictions: list[dict]


async def _save_and_validate_image(upload: UploadFile) -> tuple[Path, str, str]:
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

        with Image.open(file_path) as image:
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise HTTPException(status_code=400, detail="The file contents are not a supported JPG or PNG image.")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
                raise HTTPException(status_code=400, detail="Image dimensions exceed the supported limit.")
            image.verify()
        return file_path, unique_filename, original_filename
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded image could not be decoded. Choose a valid JPG or PNG.") from exc
    except Exception:
        file_path.unlink(missing_ok=True)
        raise


@app.exception_handler(Exception)
async def unexpected_error_handler(_request, exc: Exception):
    logger.exception("Unhandled API exception", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "An unexpected server error occurred. Please retry."})


@app.get("/")
def home():
    return {"message": "Crop Doctor AI API is running.", "version": app.version, "realtime": True}


@app.get("/health")
def health():
    model_state = model.model_status()
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
    healthy = model_state["ready"] and database_state == "healthy"
    return {
        "status": "healthy" if healthy else "degraded",
        "realtime": True,
        "connections": len(events.connections),
        "model": model_state,
        "database": database_state,
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
async def diagnose(file: UploadFile = File(...), report_key: str | None = Header(default=None, alias="X-Report-Key")):
    if (file.content_type or "").lower() not in ALLOWED_IMAGE_TYPES:
        await file.close()
        raise HTTPException(status_code=400, detail="Upload a JPG or PNG image.")
    try:
        file_path, unique_filename, original_filename = await _save_and_validate_image(file)
    finally:
        await file.close()

    job_id = str(uuid.uuid4())
    await events.broadcast("diagnosis_started", {
        "job_id": job_id,
        "filename": unique_filename,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Diagnosis started job_id=%s filename=%s", job_id, unique_filename)

    try:
        diagnosis = await asyncio.to_thread(diagnose_image, str(file_path))
        confidence = float(diagnosis["confidence"])
        needs_expert_review = bool(diagnosis.get("expert_review")) or confidence < CONFIDENCE_THRESHOLD
        alert = None
        if needs_expert_review:
            alert = await asyncio.to_thread(
                create_alert,
                crop=diagnosis["crop"],
                diagnosis=diagnosis["diagnosis"],
                severity=diagnosis["severity"],
                confidence=confidence,
                symptoms=diagnosis.get("symptoms", ""),
                image_filename=unique_filename,
            )

        response = {
            "job_id": job_id,
            "message": "Diagnosis completed successfully",
            "filename": unique_filename,
            "original_filename": original_filename,
            **diagnosis,
            "confidence": confidence,
            "expert_review": needs_expert_review,
            "alert_created": alert is not None,
            "alert": alert,
            "status": "diagnosed",
        }
        if report_key:
            stored_report = await asyncio.to_thread(save_report, response, report_key)
            response["created_at"] = stored_report["created_at"]
        await events.broadcast("diagnosis_completed", {"job_id": job_id, "diagnosis": response})
        if alert:
            await events.broadcast("alert_created", {"job_id": job_id, "alert": alert})
            logger.info("Expert alert created job_id=%s alert_id=%s", job_id, alert["id"])
        logger.info("Diagnosis completed job_id=%s crop=%s confidence=%.2f", job_id, diagnosis.get("crop"), confidence)
        return response
    except Exception as exc:
        logger.exception("Diagnosis failed job_id=%s", job_id)
        file_path.unlink(missing_ok=True)
        await events.broadcast("diagnosis_failed", {"job_id": job_id, "message": "Diagnosis could not be completed."})
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=503, detail="The diagnosis service is temporarily unavailable. Please retry.") from exc


@app.get("/alerts")
def alerts(status: Literal["pending", "in_review", "resolved"] | None = Query(default=None)):
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
def single_alert(alert_id: str):
    alert = get_alert(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    return alert


@app.patch("/alerts/{alert_id}")
async def change_alert_status(alert_id: str, update: AlertStatusUpdate):
    alert = update_alert_status(alert_id, update.status)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found.")
    await events.broadcast("alert_updated", {"alert": alert})
    logger.info("Alert updated alert_id=%s status=%s", alert_id, update.status)
    return {"message": "Alert status updated successfully", "alert": alert}
