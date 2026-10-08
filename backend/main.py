from fastapi import (
    FastAPI,
    UploadFile,
    File,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
from typing import Literal
import asyncio
import shutil
import uuid

from pydantic import BaseModel

from backend.diagnosis import diagnose_image
from backend.alerts import (
    create_alert,
    get_alerts,
    get_alert,
    update_alert_status,
)


# =========================================================
# APP
# =========================================================

app = FastAPI(
    title="Crop Disease Diagnosis API",
    description="AI-powered crop disease diagnosis and expert alert system",
    version="3.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# UPLOAD DIRECTORY
# =========================================================

UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# CONFIGURATION
# =========================================================

CONFIDENCE_THRESHOLD = 80.0


# =========================================================
# REAL-TIME EVENT HUB
# =========================================================

class EventHub:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)
        await self.send(websocket, {
            "type": "connection",
            "message": "Crop Doctor realtime channel connected",
        })

    def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)

    async def send(self, websocket: WebSocket, payload: dict):
        try:
            await websocket.send_json(payload)
        except Exception:
            self.disconnect(websocket)

    async def broadcast(self, payload: dict):
        if not self.connections:
            return

        dead = []
        for websocket in list(self.connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                dead.append(websocket)

        for websocket in dead:
            self.disconnect(websocket)


events = EventHub()


# =========================================================
# ROOT / HEALTH
# =========================================================

@app.get("/")
def home():
    return {
        "message": "Crop Disease Diagnosis API is running!",
        "version": "3.0.0",
        "realtime": True,
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "realtime": True,
        "connections": len(events.connections),
    }


# =========================================================
# WEBSOCKET REAL-TIME CHANNEL
# =========================================================

@app.websocket("/ws")
async def realtime_socket(websocket: WebSocket):
    await events.connect(websocket)

    try:
        while True:
            # Keep the connection alive and allow the browser to send
            # optional client messages in the future.
            await websocket.receive_text()
    except WebSocketDisconnect:
        events.disconnect(websocket)
    except Exception:
        events.disconnect(websocket)


# =========================================================
# DIAGNOSE CROP
# =========================================================

@app.post("/diagnose")
async def diagnose(file: UploadFile = File(...)):

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Only JPG and PNG images are allowed.",
        )

    original_filename = file.filename or "uploaded_image.jpg"
    file_extension = Path(original_filename).suffix.lower()

    if file_extension not in [".jpg", ".jpeg", ".png"]:
        raise HTTPException(
            status_code=400,
            detail="Only JPG, JPEG and PNG images are allowed.",
        )

    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_id = str(uuid.uuid4())

    await events.broadcast({
        "type": "diagnosis_started",
        "job_id": job_id,
        "filename": unique_filename,
        "original_filename": original_filename,
        "timestamp": asyncio.get_running_loop().time(),
    })

    try:
        # TensorFlow inference is moved off the FastAPI event loop so
        # WebSocket clients remain responsive during model prediction.
        diagnosis = await asyncio.to_thread(
            diagnose_image,
            str(file_path),
        )
    except Exception as exc:
        await events.broadcast({
            "type": "diagnosis_failed",
            "job_id": job_id,
            "filename": unique_filename,
            "error": str(exc),
        })
        raise

    await events.broadcast({
        "type": "diagnosis_completed",
        "job_id": job_id,
        "filename": unique_filename,
        "diagnosis": diagnosis,
    })

    needs_expert_review = (
        diagnosis["expert_review"]
        or diagnosis["confidence"] < CONFIDENCE_THRESHOLD
    )

    alert = None

    if needs_expert_review:
        alert = create_alert(
            crop=diagnosis["crop"],
            diagnosis=diagnosis["diagnosis"],
            severity=diagnosis["severity"],
            confidence=diagnosis["confidence"],
            symptoms=diagnosis["symptoms"],
            image_filename=unique_filename,
        )

        await events.broadcast({
            "type": "alert_created",
            "job_id": job_id,
            "alert": alert,
        })

    return {
        "message": "Diagnosis completed successfully",
        "filename": unique_filename,
        "original_filename": original_filename,
        **diagnosis,
        "expert_review": needs_expert_review,
        "alert_created": alert is not None,
        "alert": alert,
        "status": "diagnosed",
    }


# =========================================================
# GET ALERTS
# =========================================================

@app.get("/alerts")
def alerts(status: str | None = None):
    current = get_alerts(status)
    return {
        "count": len(current),
        "alerts": current,
    }


# =========================================================
# GET SINGLE ALERT
# =========================================================

@app.get("/alerts/{alert_id}")
def single_alert(alert_id: str):
    alert = get_alert(alert_id)

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found.",
        )

    return alert


# =========================================================
# ALERT STATUS MODEL
# =========================================================

class AlertStatusUpdate(BaseModel):
    status: Literal[
        "pending",
        "in_review",
        "resolved",
    ]


# =========================================================
# UPDATE ALERT STATUS
# =========================================================

@app.patch("/alerts/{alert_id}")
async def change_alert_status(
    alert_id: str,
    update: AlertStatusUpdate,
):
    alert = update_alert_status(
        alert_id,
        update.status,
    )

    if alert is None:
        raise HTTPException(
            status_code=404,
            detail="Alert not found.",
        )

    await events.broadcast({
        "type": "alert_updated",
        "alert": alert,
    })

    return {
        "message": "Alert status updated successfully",
        "alert": alert,
    }
