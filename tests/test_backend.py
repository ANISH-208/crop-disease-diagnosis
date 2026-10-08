"""Focused regression tests using only the Python standard library."""

import asyncio
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import Headers

from backend import alerts, main, model


PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def asgi_request(method: str, path: str, body: bytes = b"", headers=()):
    """Exercise the FastAPI ASGI stack without opening a network port."""
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    await main.app(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": list(headers),
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(response_body) if response_body else None


class ApiContractTests(unittest.TestCase):
    def test_health_and_list_routes_over_asgi(self):
        root_status, root = asyncio.run(asgi_request("GET", "/"))
        health_status, health = asyncio.run(asgi_request("GET", "/health"))
        alerts_status, alert_list = asyncio.run(asgi_request("GET", "/alerts"))
        self.assertEqual(root_status, 200)
        self.assertEqual(root["version"], main.app.version)
        self.assertEqual(health_status, 200)
        self.assertIn("database", health)
        self.assertEqual(alerts_status, 200)
        self.assertEqual(alert_list["count"], len(alert_list["alerts"]))

    def test_root_endpoint_returns_api_version(self):
        response = main.home()
        self.assertEqual(response["version"], main.app.version)
        self.assertTrue(response["realtime"])

    def test_health_includes_model_readiness_and_connection_count(self):
        response = main.health()
        self.assertIn(response["status"], {"healthy", "degraded"})
        self.assertIn("model", response)
        self.assertIn("connections", response)

    def test_disease_reference_matches_all_model_classes(self):
        response = main.diseases()
        self.assertEqual(response["count"], 38)
        self.assertEqual({item["class"] for item in response["classes"]}, set(model.CLASS_NAMES))
        self.assertTrue(all(item["symptoms"] and item["prevention"] for item in response["classes"]))

    def test_alert_list_keeps_count_and_items_in_sync(self):
        rows = [{"id": "case-1", "status": "pending"}]
        with patch.object(main, "get_alerts", return_value=rows):
            response = main.alerts()
        self.assertEqual(response, {"count": 1, "alerts": rows})

    def test_patch_response_is_wrapped_and_broadcast(self):
        alert = {"id": "case-1", "status": "in_review"}
        broadcast = AsyncMock()
        with patch.object(main, "update_alert_status", return_value=alert), patch.object(main.events, "broadcast", broadcast):
            response = asyncio.run(main.change_alert_status("case-1", main.AlertStatusUpdate(status="in_review")))
        self.assertEqual(response["alert"], alert)
        broadcast.assert_awaited_once_with("alert_updated", {"alert": alert})

    def test_patch_missing_alert_returns_404(self):
        with patch.object(main, "update_alert_status", return_value=None):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.change_alert_status("missing", main.AlertStatusUpdate(status="resolved")))
        self.assertEqual(raised.exception.status_code, 404)

    def test_invalid_status_is_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            main.AlertStatusUpdate(status="closed")

    def test_alert_database_persistence_and_priority(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "alerts.db"
            with patch.object(alerts, "DATABASE_PATH", database):
                alerts.initialize_database()
                created = alerts.create_alert("Tomato", "Early Blight", "Moderate", 78.2, "Leaf spots", "leaf.png")
                self.assertEqual(created["priority"], "medium")
                self.assertEqual(alerts.get_alert(created["id"])["status"], "pending")
                updated = alerts.update_alert_status(created["id"], "in_review")
                self.assertEqual(updated["status"], "in_review")
                self.assertEqual(alerts.get_alerts("in_review")[0]["id"], created["id"])

    def test_upload_rejects_wrong_media_type(self):
        upload = UploadFile(
            file=io.BytesIO(b"not an image"),
            filename="leaf.gif",
            headers=Headers({"content-type": "image/gif"}),
        )
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main.diagnose(upload))
        self.assertEqual(raised.exception.status_code, 400)

    def test_upload_rejects_invalid_image_bytes_and_removes_temporary_file(self):
        upload = UploadFile(
            file=io.BytesIO(b"not a JPEG"),
            filename="leaf.jpg",
            headers=Headers({"content-type": "image/jpeg"}),
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main._save_and_validate_image(upload))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_upload_enforces_size_limit(self):
        buffer = io.BytesIO()
        Image.new("RGB", (20, 20), color="green").save(buffer, format="JPEG")
        upload = UploadFile(
            file=io.BytesIO(buffer.getvalue()),
            filename="leaf.jpg",
            headers=Headers({"content-type": "image/jpeg"}),
        )
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)), patch.object(main, "MAX_UPLOAD_BYTES", 12):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main._save_and_validate_image(upload))
            self.assertEqual(raised.exception.status_code, 413)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_diagnosis_creates_and_broadcasts_expert_alert(self):
        buffer = io.BytesIO()
        Image.new("RGB", (24, 24), color="green").save(buffer, format="PNG")
        upload = UploadFile(
            file=io.BytesIO(buffer.getvalue()),
            filename="leaf.png",
            headers=Headers({"content-type": "image/png"}),
        )
        predicted = {
            "crop": "Apple", "diagnosis": "Apple Scab", "confidence": 92.5,
            "severity": "Moderate", "symptoms": "Olive spots", "prevention": ["Remove affected leaves"],
            "expert_review": True, "model_version": model.MODEL_VERSION,
            "top_predictions": [{"class": "Apple___Apple_scab", "confidence": 92.5}],
        }
        alert = {"id": "case-2", "status": "pending", "crop": "Apple"}
        with tempfile.TemporaryDirectory() as directory:
            broadcaster = AsyncMock()
            with patch.object(main, "UPLOAD_DIR", Path(directory)), \
                 patch.object(main, "diagnose_image", return_value=predicted), \
                 patch.object(main, "create_alert", return_value=alert), \
                 patch.object(main.events, "broadcast", broadcaster):
                response = asyncio.run(main.diagnose(upload))
            self.assertTrue(response["alert_created"])
            self.assertEqual(response["alert"], alert)
            self.assertTrue((Path(directory) / response["filename"]).is_file())
            event_types = [call.args[0] for call in broadcaster.await_args_list]
            self.assertEqual(event_types, ["diagnosis_started", "diagnosis_completed", "alert_created"])

    def test_multipart_diagnosis_route_returns_valid_report(self):
        buffer = io.BytesIO()
        Image.new("RGB", (24, 24), color="green").save(buffer, format="PNG")
        boundary = b"cropdoctor-boundary"
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="leaf.png"\r\n'
            b"Content-Type: image/png\r\n\r\n" + buffer.getvalue() + b"\r\n"
            b"--" + boundary + b"--\r\n"
        )
        diagnosis = {
            "crop": "Apple", "diagnosis": "Healthy", "confidence": 99.1,
            "severity": "None", "symptoms": "No represented disease signs.",
            "prevention": ["Continue monitoring."], "expert_review": False,
            "model_version": model.MODEL_VERSION,
            "top_predictions": [{"class": "Apple___healthy", "confidence": 99.1}],
        }
        broadcaster = AsyncMock()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(main, "UPLOAD_DIR", Path(directory)), \
             patch.object(main, "diagnose_image", return_value=diagnosis), \
             patch.object(main.events, "broadcast", broadcaster):
            status_code, response = asyncio.run(asgi_request(
                "POST", "/diagnose", body,
                [(b"content-type", b"multipart/form-data; boundary=cropdoctor-boundary")],
            ))
        self.assertEqual(status_code, 200, response)
        self.assertEqual(response["crop"], "Apple")
        self.assertFalse(response["alert_created"])
        self.assertEqual(response["model_version"], model.MODEL_VERSION)


class ModelIntegrationTests(unittest.TestCase):
    def test_v6_model_loads_and_classifies_a_held_out_plantvillage_image(self):
        self.assertEqual(len(model.CLASS_NAMES), 38)
        manifest = PROJECT_ROOT / "ml_v6" / "datasets" / "dataset_manifest.csv"
        if not manifest.exists():
            self.skipTest("PlantVillage manifest is not present in this checkout.")

        with manifest.open(newline="", encoding="utf-8") as stream:
            row = next((item for item in csv.DictReader(stream) if item["split"] == "test"), None)
        if row is None:
            self.skipTest("Manifest contains no held-out test example.")
        image_path = PROJECT_ROOT / row["image_path"]
        if not image_path.is_file():
            self.skipTest("The referenced PlantVillage image is not installed locally.")

        result = model.predict_disease(image_path)
        self.assertIn(result["class"], model.CLASS_NAMES)
        self.assertEqual(result["model_version"], model.MODEL_VERSION)
        self.assertEqual(len(result["top_predictions"]), 3)
        self.assertTrue(all(0 <= item["confidence"] <= 100 for item in result["top_predictions"]))


if __name__ == "__main__":
    unittest.main()
