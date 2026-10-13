"""Disease prediction with explicit input validation and uncertainty policy."""

from backend import model
from backend.config import DISEASE_MIN_MARGIN, DISEASE_MIN_PROBABILITY
from backend.disease_data import DISEASE_DATA


class SuitabilityRequiredError(RuntimeError):
    """Raised if disease classification is attempted without a positive gate."""


def disease_policy_status() -> dict:
    try:
        minimum_probability = float(DISEASE_MIN_PROBABILITY) if DISEASE_MIN_PROBABILITY is not None else None
        minimum_margin = float(DISEASE_MIN_MARGIN) if DISEASE_MIN_MARGIN is not None else None
        ready = (
            minimum_probability is not None
            and minimum_margin is not None
            and 0 <= minimum_probability <= 1
            and 0 <= minimum_margin <= 1
        )
    except (TypeError, ValueError):
        ready = False
    return {
        "status": "configured" if ready else "unconfigured",
        "ready": ready,
        "message": None if ready else "Calibrated disease probability and margin thresholds are not configured.",
    }


def diagnose_image(image_path: str, suitability_result: dict | None = None) -> dict:
    """Run disease inference only after a validated suitable result.

    The acceptance thresholds must come from a held-out calibration process.
    Until both are configured, the class scores are returned as uncertain and
    never promoted to a diagnosis.
    """
    if not suitability_result or suitability_result.get("status") != "suitable":
        raise SuitabilityRequiredError("Disease classification requires a suitable crop/leaf validation result.")

    result = model.predict_disease(image_path)
    top = result["top_predictions"]
    confidence = float(result["confidence"])
    # The displayed top predictions are rounded to two decimal places. Use
    # the raw model probabilities for the calibrated acceptance margin so the
    # runtime decision matches the calibration script exactly.
    probabilities = result.get("probabilities", [])
    if len(probabilities) > 1:
        second_probability = sorted((float(value) for value in probabilities), reverse=True)[1]
    elif len(top) > 1:
        second_probability = float(top[1]["confidence"]) / 100
    else:
        second_probability = 0.0
    margin = confidence - second_probability
    policy = disease_policy_status()
    if not policy["ready"]:
        return _uncertain_result(result, "Disease prediction thresholds have not been calibrated.")

    minimum_probability = float(DISEASE_MIN_PROBABILITY)
    minimum_margin = float(DISEASE_MIN_MARGIN)
    if confidence < minimum_probability or margin < minimum_margin:
        return _uncertain_result(result, "The model scores do not meet the configured confidence and separation requirements.")

    predicted_class = result["class"]
    disease_info = DISEASE_DATA.get(
        predicted_class,
        {
            "crop": predicted_class.split("___")[0],
            "disease": predicted_class.split("___")[-1].replace("_", " "),
            "severity": "Unknown",
            "symptoms": "Detailed information is not currently available.",
            "prevention": [
                "Monitor the crop regularly.",
                "Consult a local agricultural expert for confirmation.",
            ],
            "expert_review": True,
        },
    )
    healthy_prediction = disease_info["disease"].strip().lower() == "healthy"
    return {
        "status": "healthy_class_predicted" if healthy_prediction else "possible_disease_detected",
        "message": "The model found a possible match. Confirm important crop decisions with a local expert.",
        "crop": disease_info["crop"],
        "diagnosis": disease_info["disease"],
        "confidence": round(confidence * 100, 2),
        "severity": disease_info["severity"],
        "symptoms": disease_info["symptoms"],
        "prevention": disease_info["prevention"],
        "expert_review": bool(disease_info["expert_review"]),
        "model_version": result["model_version"],
        "top_predictions": top,
    }


def _uncertain_result(result: dict, reason: str) -> dict:
    return {
        "status": "uncertain",
        "message": "We could not confirm a crop condition from this photo. Try a clear, close photo of one leaf, or ask a local crop expert.",
        "uncertainty_reason": reason,
        "crop": None,
        "diagnosis": None,
        "confidence": round(float(result["confidence"]) * 100, 2),
        "severity": None,
        "symptoms": None,
        "prevention": [],
        "expert_review": True,
        "model_version": result["model_version"],
        "top_predictions": result["top_predictions"],
    }
