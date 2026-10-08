from backend.model import predict_disease
from backend.disease_data import DISEASE_DATA


def diagnose_image(image_path: str) -> dict:
    result = predict_disease(image_path)

    predicted_class = result["class"]
    confidence = result["confidence"]

    disease_info = DISEASE_DATA.get(
        predicted_class,
        {
            "crop": predicted_class.split("___")[0],
            "disease": predicted_class.split("___")[-1].replace("_", " "),
            "severity": "Unknown",
            "symptoms": "Detailed information is not currently available.",
            "prevention": [
                "Monitor the crop regularly.",
                "Consult a local agricultural expert for confirmation."
            ],
            "expert_review": True
        }
    )

    return {
        "crop": disease_info["crop"],
        "diagnosis": disease_info["disease"],
        "confidence": round(confidence * 100, 2),
        "severity": disease_info["severity"],
        "symptoms": disease_info["symptoms"],
        "prevention": disease_info["prevention"],
        "expert_review": disease_info["expert_review"],

        # V6 model telemetry
        "model_version": result["model_version"],
        "top_predictions": result["top_predictions"]
    }
