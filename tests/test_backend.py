"""Backend contracts, image safety, suitability gating, alerts, and real inference."""

import asyncio
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers
from starlette.websockets import WebSocketDisconnect

from backend import alerts, diagnosis, main, model
from backend.image_utils import load_normalized_rgb
from backend.suitability import CropSuitabilityValidator

PROJECT_ROOT = Path(__file__).resolve().parents[1]


async def asgi_request(method: str, path: str, body: bytes = b"", headers=()):
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
            "type": "http", "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1", "method": method, "scheme": "http", "path": path,
            "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": list(headers), "client": ("testclient", 123), "server": ("testserver", 80),
        }, receive, send,
    )
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_body = b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body")
    return start["status"], json.loads(response_body) if response_body else None


def image_upload(*, image_format="PNG", filename="leaf.png", media_type="image/png", size=(32, 24), mode="RGB"):
    buffer = io.BytesIO()
    Image.new(mode, size, color=0 if mode == "L" else (35, 120, 54)).save(buffer, format=image_format)
    return UploadFile(file=io.BytesIO(buffer.getvalue()), filename=filename, headers=Headers({"content-type": media_type}))


class FakeWebSocket:
    def __init__(self):
        self.accepted = False
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        self.sent.append(payload)

    async def receive_text(self):
        raise WebSocketDisconnect(code=1000)


class ApiContractTests(unittest.TestCase):
    def test_root_and_health_report_realtime_and_safe_readiness(self):
        root_status, root = asyncio.run(asgi_request("GET", "/"))
        health_status, health = asyncio.run(asgi_request("GET", "/health"))
        self.assertEqual(root_status, 200)
        self.assertEqual(root["version"], main.app.version)
        self.assertEqual(root["realtime"], main.REALTIME_AVAILABLE)
        self.assertEqual(health_status, 200)
        self.assertIn(health["status"], {"healthy", "degraded"})
        self.assertIn("model", health)
        self.assertIn("suitability", health)
        self.assertIn("disease_policy", health)
        self.assertIn("diagnosis_ready", health)
        self.assertIn("database_persistence", health)

    def test_disease_reference_matches_all_model_classes(self):
        response = main.diseases()
        self.assertEqual(response["count"], 38)
        self.assertEqual({item["class"] for item in response["classes"]}, set(model.CLASS_NAMES))
        self.assertTrue(all(item["symptoms"] and item["prevention"] for item in response["classes"]))

    def test_missing_class_mapping_degrades_without_crashing_import(self):
        with patch.object(model, "_mapping_error", "missing mapping"), patch.object(model, "CLASS_NAMES", []):
            self.assertEqual(model.model_status()["status"], "mapping_error")

    def test_http_errors_have_structured_messages_without_tracebacks(self):
        status_code, response = asyncio.run(asgi_request(
            "POST", "/diagnose", b"", [(b"content-type", b"application/json")],
        ))
        self.assertEqual(status_code, 422)
        self.assertEqual(response["status"], "invalid_image")
        self.assertIn("photo", response["message"].lower())
        self.assertNotIn("traceback", json.dumps(response).lower())

    def test_expert_endpoints_require_access_and_keep_alert_contract(self):
        expert_key = "test-expert-key-that-is-longer-than-thirty-two-characters"
        with patch.object(main, "EXPERT_API_KEY", expert_key):
            unauthenticated_statuses = [
                asyncio.run(asgi_request("GET", "/alerts"))[0],
                asyncio.run(asgi_request("GET", "/alerts/case-1"))[0],
                asyncio.run(asgi_request(
                    "PATCH", "/alerts/case-1", b'{"status":"resolved"}',
                    [(b"content-type", b"application/json")],
                ))[0],
            ]
            with patch.object(main, "get_alerts", return_value=[]), \
                 patch.object(main, "get_alert", return_value={"id": "case-1"}), \
                 patch.object(main, "update_alert_status", return_value={"id": "case-1", "status": "resolved"}), \
                 patch.object(main.events, "broadcast", AsyncMock()):
                alerts_status, payload = asyncio.run(asgi_request(
                    "GET", "/alerts", headers=[(b"x-expert-key", expert_key.encode())],
                ))
                single_status, single = asyncio.run(asgi_request(
                    "GET", "/alerts/case-1", headers=[(b"x-expert-key", expert_key.encode())],
                ))
                patch_status, updated = asyncio.run(asgi_request(
                    "PATCH", "/alerts/case-1", b'{"status":"resolved"}',
                    [(b"content-type", b"application/json"), (b"x-expert-key", expert_key.encode())],
                ))
        self.assertEqual(unauthenticated_statuses, [401, 401, 401])
        self.assertEqual(alerts_status, 200)
        self.assertEqual(payload["count"], len(payload["alerts"]))
        self.assertEqual(single_status, 200)
        self.assertEqual(single["id"], "case-1")
        self.assertEqual(patch_status, 200)
        self.assertEqual(updated["alert"]["status"], "resolved")

    def test_alert_database_persistence_and_status_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "alerts.db"
            with patch.object(alerts, "DATABASE_PATH", database):
                alerts.initialize_database()
                created = alerts.create_alert("Tomato", "Early Blight", "Moderate", 78.2, "Leaf spots", None, "crop-check-v1")
                self.assertEqual(created["priority"], "medium")
                self.assertEqual(created["image_filename"], None)
                self.assertEqual(created["validation_model_version"], "crop-check-v1")
                self.assertEqual(alerts.get_alert(created["id"])["status"], "pending")
                updated = alerts.update_alert_status(created["id"], "in_review")
                self.assertEqual(updated["status"], "in_review")
                self.assertEqual(alerts.get_alerts("in_review")[0]["id"], created["id"])
                report = alerts.save_report({
                    "job_id": "report-1", "crop": "Tomato", "diagnosis": "Early Blight",
                    "confidence": 78.2, "severity": "Moderate", "symptoms": "Leaf spots",
                    "prevention": ["Remove affected leaves."], "expert_review": True, "alert": None,
                    "validation": {"model_version": "crop-check-v1"}, "status": "possible_disease_detected",
                }, "report-key-" + "r" * 32)
                alerts.link_report_to_alert(report["id"], created["id"])
                saved = alerts.get_reports("report-key-" + "r" * 32)
                other_owner = alerts.get_reports("another-report-key-" + "r" * 32)
                self.assertEqual(report["id"], "report-1")
                self.assertEqual(saved[0]["prevention"], ["Remove affected leaves."])
                self.assertEqual(saved[0]["status"], "in_review")
                self.assertEqual(other_owner, [])
                legacy = alerts.save_report({
                    "job_id": "legacy-report", "crop": "Potato", "diagnosis": "Early Blight",
                    "confidence": 99, "severity": "Moderate", "symptoms": "Spots",
                    "prevention": [], "expert_review": False,
                }, "report-key-" + "r" * 32)
                legacy_report = next(row for row in alerts.get_reports("report-key-" + "r" * 32) if row["id"] == legacy["id"])
                self.assertEqual(legacy_report["status"], "legacy_unvalidated")
                self.assertIsNone(legacy_report["diagnosis"])

    def test_alert_status_patch_broadcasts_matching_alert(self):
        alert = {"id": "case-1", "status": "in_review"}
        broadcast = AsyncMock()
        with patch.object(main, "update_alert_status", return_value=alert), patch.object(main.events, "broadcast", broadcast):
            response = asyncio.run(main.change_alert_status("case-1", main.AlertStatusUpdate(status="in_review")))
        self.assertEqual(response["alert"], alert)
        broadcast.assert_awaited_once_with("alert_updated", {"alert": alert})

    def test_alert_status_rejects_unknown_values(self):
        with self.assertRaises(Exception):
            main.AlertStatusUpdate(status="closed")

    def test_websocket_connection_and_event_envelope(self):
        websocket = FakeWebSocket()
        asyncio.run(main.realtime_socket(websocket))
        self.assertTrue(websocket.accepted)
        self.assertEqual(websocket.sent[0]["type"], "connection")
        self.assertTrue(websocket.sent[0]["event_id"])

        async def publish():
            await main.events.broadcast("alert_updated", {"alert": {"id": "case-1"}})

        second = FakeWebSocket()
        main.events.connections.add(second)
        try:
            asyncio.run(publish())
        finally:
            main.events.disconnect(second)
        self.assertEqual(second.sent[0]["type"], "alert_updated")
        self.assertEqual(second.sent[0]["data"]["alert"]["id"], "case-1")
        self.assertTrue(second.sent[0]["event_id"])


class ImageValidationTests(unittest.TestCase):
    def test_upload_rejects_wrong_type_and_invalid_bytes_and_removes_temp_files(self):
        wrong_type = image_upload(image_format="PNG", filename="leaf.gif", media_type="image/gif")
        with self.assertRaises(HTTPException) as raised:
            asyncio.run(main._save_and_validate_image(wrong_type))
        self.assertEqual(raised.exception.status_code, 400)

        invalid = UploadFile(file=io.BytesIO(b"not an image"), filename="leaf.jpg", headers=Headers({"content-type": "image/jpeg"}))
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main._save_and_validate_image(invalid))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_upload_enforces_size_and_detected_format(self):
        upload = image_upload()
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)), patch.object(main, "MAX_UPLOAD_BYTES", 12):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main._save_and_validate_image(upload))
            self.assertEqual(raised.exception.status_code, 413)
            self.assertEqual(list(Path(directory).iterdir()), [])

        mismatch = image_upload(image_format="PNG", filename="leaf.jpg", media_type="image/jpeg")
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main._save_and_validate_image(mismatch))
            self.assertEqual(raised.exception.status_code, 400)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_image_normalization_converts_grayscale_and_alpha_to_rgb(self):
        with tempfile.TemporaryDirectory() as directory:
            gray_path = Path(directory) / "gray.png"
            Image.new("L", (18, 12), color=120).save(gray_path)
            normalized = load_normalized_rgb(gray_path)
            self.assertEqual(normalized.mode, "RGB")
            self.assertEqual(normalized.size, (18, 12))
            normalized.close()
            rgba_path = Path(directory) / "alpha.png"
            Image.new("RGBA", (8, 6), color=(20, 90, 30, 0)).save(rgba_path)
            normalized = load_normalized_rgb(rgba_path)
            self.assertEqual(normalized.getpixel((0, 0)), (255, 255, 255))
            normalized.close()

    def test_path_like_filename_is_replaced_with_random_server_path(self):
        upload = image_upload(filename="../../sensitive-name.png")
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)):
            path = asyncio.run(main._save_and_validate_image(upload))
            self.assertEqual(path.parent, Path(directory))
            self.assertNotIn("sensitive-name", path.name)
            path.unlink()


class SuitabilityGateTests(unittest.TestCase):
    def test_missing_validator_fails_closed_and_reports_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            validator = CropSuitabilityValidator(Path(directory) / "missing.tflite")
            self.assertFalse(validator.status()["ready"])
            result = validator.validate_image(Path(directory) / "nonexistent.jpg")
            self.assertEqual(result["status"], "unavailable")

    def test_not_plant_response_stops_before_disease_classifier(self):
        upload = image_upload()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(main, "UPLOAD_DIR", Path(directory)), \
             patch.object(main.suitability_validator, "validate_image", return_value={"status": "not_plant", "score": 0.1, "threshold": 0.7}), \
             patch.object(main, "diagnose_image") as classifier:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.diagnose(upload, None))
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(raised.exception.status_code, 422)
        self.assertEqual(raised.exception.detail["status"], "not_plant")
        classifier.assert_not_called()

    def test_missing_validator_response_stops_before_disease_classifier(self):
        upload = image_upload()
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(main, "UPLOAD_DIR", Path(directory)), \
             patch.object(main.suitability_validator, "validate_image", return_value={"status": "unavailable", "message": "Not installed."}), \
             patch.object(main, "diagnose_image") as classifier:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.diagnose(upload, None))
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.detail["status"], "validation_unavailable")
        classifier.assert_not_called()

    def test_disease_policy_returns_uncertain_when_uncalibrated(self):
        output = {
            "class": "Apple___Apple_scab", "confidence": 0.91, "model_version": model.MODEL_VERSION,
            "top_predictions": [
                {"class": "Apple___Apple_scab", "confidence": 91.0},
                {"class": "Apple___healthy", "confidence": 5.0},
                {"class": "Apple___Black_rot", "confidence": 2.0},
            ],
        }
        with patch.object(diagnosis.model, "predict_disease", return_value=output), \
             patch.object(diagnosis, "DISEASE_MIN_PROBABILITY", None), \
             patch.object(diagnosis, "DISEASE_MIN_MARGIN", None):
            result = diagnosis.diagnose_image("unused.jpg", {"status": "suitable"})
        self.assertEqual(result["status"], "uncertain")
        self.assertIsNone(result["diagnosis"])
        self.assertTrue(result["expert_review"])

    def test_disease_model_cannot_run_without_suitability_result(self):
        with patch.object(diagnosis.model, "predict_disease") as classifier:
            with self.assertRaises(diagnosis.SuitabilityRequiredError):
                diagnosis.diagnose_image("unused.jpg")
        classifier.assert_not_called()


class DiagnosisRouteTests(unittest.TestCase):
    def test_short_report_key_is_rejected_before_saving_the_upload(self):
        upload = image_upload()
        with tempfile.TemporaryDirectory() as directory, patch.object(main, "UPLOAD_DIR", Path(directory)):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.diagnose(upload, "short"))
            self.assertEqual(raised.exception.status_code, 422)
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertTrue(upload.file.closed)

    def test_diagnose_route_rejects_short_report_key_with_422(self):
        boundary = b"short-key-boundary"
        image = io.BytesIO()
        Image.new("RGB", (12, 12), color=(35, 120, 54)).save(image, format="PNG")
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="leaf.png"\r\n'
            b"Content-Type: image/png\r\n\r\n" + image.getvalue() + b"\r\n"
            b"--" + boundary + b"--\r\n"
        )
        status_code, response = asyncio.run(asgi_request(
            "POST",
            "/diagnose",
            body,
            [
                (b"content-type", b"multipart/form-data; boundary=short-key-boundary"),
                (b"x-report-key", b"short"),
            ],
        ))
        self.assertEqual(status_code, 422)
        self.assertEqual(response["status"], "invalid_request")

    def test_successful_diagnosis_contract_and_cleanup(self):
        upload = image_upload()
        predicted = {
            "status": "possible_disease_detected", "message": "Possible match.", "crop": "Apple",
            "diagnosis": "Apple Scab", "confidence": 92.5, "severity": "Moderate",
            "symptoms": "Olive spots", "prevention": ["Remove affected leaves"], "expert_review": True,
            "model_version": model.MODEL_VERSION, "top_predictions": [{"class": "Apple___Apple_scab", "confidence": 92.5}],
        }
        alert = {"id": "case-2", "status": "pending", "crop": "Apple"}
        with tempfile.TemporaryDirectory() as directory:
            upload_dir = Path(directory)
            broadcaster = AsyncMock()
            operation_order = []
            with patch.object(main, "UPLOAD_DIR", Path(directory)), \
                 patch.object(main.suitability_validator, "validate_image", return_value={"status": "suitable", "score": 0.99, "threshold": 0.7, "model_version": "plant-check-v1"}), \
                 patch.object(main, "diagnose_image", return_value=predicted), \
                 patch.object(main, "create_alert", side_effect=lambda **_kwargs: operation_order.append("create_alert") or alert), \
                 patch.object(main, "save_report", side_effect=lambda report, _key: operation_order.append("save_report") or {**report, "created_at": "2026-01-01T00:00:00+00:00"}), \
                 patch.object(main, "link_report_to_alert", side_effect=lambda *_args: operation_order.append("link_report_to_alert")), \
                 patch.object(main.events, "broadcast", broadcaster):
                response = asyncio.run(main.diagnose(upload, "r" * 32))
            self.assertEqual(list(upload_dir.iterdir()), [])
        self.assertEqual(response["status"], "possible_disease_detected")
        self.assertEqual(response["crop"], "Apple")
        self.assertEqual(response["alert"], alert)
        self.assertTrue(response["alert_created"])
        self.assertEqual(response["validation"]["model_version"], "plant-check-v1")
        self.assertEqual(operation_order, ["save_report", "create_alert", "link_report_to_alert"])
        self.assertEqual([call.args[0] for call in broadcaster.await_args_list], ["diagnosis_started", "diagnosis_completed", "alert_created"])
        alert_event = next(call.args for call in broadcaster.await_args_list if call.args[0] == "alert_created")
        self.assertEqual(alert_event[1]["alert"]["id"], "case-2")

    def test_report_save_failure_does_not_create_an_expert_alert(self):
        upload = image_upload()
        predicted = {
            "status": "possible_disease_detected", "message": "Possible match.", "crop": "Apple",
            "diagnosis": "Apple Scab", "confidence": 92.5, "severity": "Moderate",
            "symptoms": "Olive spots", "prevention": [], "expert_review": True,
            "model_version": model.MODEL_VERSION, "top_predictions": [],
        }
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(main, "UPLOAD_DIR", Path(directory)), \
             patch.object(main.suitability_validator, "validate_image", return_value={"status": "suitable", "model_version": "plant-check-v1"}), \
             patch.object(main, "diagnose_image", return_value=predicted), \
             patch.object(main, "save_report", side_effect=RuntimeError("database unavailable")), \
             patch.object(main, "create_alert") as create_alert, \
             patch.object(main.events, "broadcast", AsyncMock()):
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(main.diagnose(upload, "r" * 32))
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(raised.exception.status_code, 503)
        create_alert.assert_not_called()

    def test_multipart_route_returns_uncertain_without_storing_a_report(self):
        buffer = io.BytesIO()
        Image.new("RGB", (24, 24), color=(25, 110, 40)).save(buffer, format="PNG")
        boundary = b"cropdoctor-boundary"
        body = (
            b"--" + boundary + b"\r\n"
            b'Content-Disposition: form-data; name="file"; filename="leaf.png"\r\n'
            b"Content-Type: image/png\r\n\r\n" + buffer.getvalue() + b"\r\n"
            b"--" + boundary + b"--\r\n"
        )
        uncertain = {
            "status": "uncertain", "message": "We could not confirm a crop condition.", "crop": None,
            "diagnosis": None, "confidence": 64.0, "severity": None, "symptoms": None,
            "prevention": [], "expert_review": True, "model_version": model.MODEL_VERSION, "top_predictions": [],
        }
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(main, "UPLOAD_DIR", Path(directory)), \
             patch.object(main.suitability_validator, "validate_image", return_value={"status": "suitable", "score": 0.99, "threshold": 0.7, "model_version": "plant-check-v1"}), \
             patch.object(main, "diagnose_image", return_value=uncertain), \
             patch.object(main, "save_report") as save_report, \
             patch.object(main.events, "broadcast", AsyncMock()):
            status_code, response = asyncio.run(asgi_request(
                "POST", "/diagnose", body,
                [(b"content-type", b"multipart/form-data; boundary=cropdoctor-boundary"), (b"x-report-key", b"r" * 32)],
            ))
            self.assertEqual(list(Path(directory).iterdir()), [])
        self.assertEqual(status_code, 200, response)
        self.assertEqual(response["status"], "uncertain")
        self.assertIsNone(response["diagnosis"])
        save_report.assert_not_called()


class ModelIntegrationTests(unittest.TestCase):
    def test_committed_litert_model_runs_on_a_synthetic_image(self):
        lite_model = PROJECT_ROOT / "models" / "crop_doctor_v6_efficientnetv2s.tflite"
        self.assertTrue(lite_model.is_file(), "The committed LiteRT model artifact is required.")
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "synthetic.png"
            Image.new("RGB", (320, 240), color=(46, 112, 63)).save(image_path)
            with patch.object(model, "LITE_MODEL_PATH", lite_model), \
                 patch.object(model, "MODEL_PATH", Path(directory) / "model.keras"), \
                 patch.object(model, "_model", None), \
                 patch.object(model, "_active_runtime", None), \
                 patch.object(model, "_load_error", None):
                result = model.predict_disease(image_path)
                active_runtime = model._active_runtime

        self.assertEqual(active_runtime, "tflite")
        self.assertIn(result["class"], model.CLASS_NAMES)
        self.assertEqual(len(result["probabilities"]), model.EXPECTED_CLASS_COUNT)
        self.assertTrue(all(0 <= probability <= 1 for probability in result["probabilities"]))
        self.assertEqual(len(result["top_predictions"]), 3)

    def test_v6_model_runs_on_a_real_held_out_plantvillage_image(self):
        self.assertEqual(len(model.CLASS_NAMES), 38)
        manifest = PROJECT_ROOT / "ml_v6" / "datasets" / "dataset_manifest.csv"
        if manifest.exists():
            import csv
            with manifest.open(newline="", encoding="utf-8") as stream:
                import_row = next((row for row in csv.DictReader(stream) if row["split"] == "test"), None)
            if import_row:
                image_path = Path(import_row["image_path"])
                if not image_path.is_absolute():
                    image_path = PROJECT_ROOT / image_path
                expected_index = model.CLASS_NAMES.index(import_row["canonical_label"])
            else:
                image_path, expected_index = self._bundled_test_image()
        else:
            image_path, expected_index = self._bundled_test_image()
        if not image_path.is_file():
            self.skipTest("No held-out PlantVillage image is installed locally.")
        result = model.predict_disease(image_path)
        self.assertEqual(result["class"], model.CLASS_NAMES[expected_index])
        self.assertEqual(result["model_version"], "v6-efficientnetv2s")
        self.assertEqual(len(result["top_predictions"]), 3)
        self.assertTrue(all(0 <= item["confidence"] <= 100 for item in result["top_predictions"]))

    @staticmethod
    def _bundled_test_image() -> tuple[Path, int]:
        folder = PROJECT_ROOT / "ml_v6" / "datasets" / "PlantVillage" / "data_distribution_for_SVM" / "test" / "0"
        images = sorted(path for path in folder.iterdir() if path.is_file()) if folder.is_dir() else []
        return (images[0], 0) if images else (folder / "missing.jpg", 0)


if __name__ == "__main__":
    unittest.main()
