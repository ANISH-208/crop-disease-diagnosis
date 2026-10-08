from backend.diagnosis import diagnose_image
from pathlib import Path


# Change this to your test image
image_path = "backend/uploads/8314ea99-42f8-4d77-b0d3-7caa40949d69.jpeg"

# Check that the image exists
if not Path(image_path).exists():
    print(f"❌ Image not found: {image_path}")
    exit()


# Run complete diagnosis
result = diagnose_image(image_path)


print("\n")
print("=" * 50)
print("       🌱 CROP DISEASE DIAGNOSIS")
print("=" * 50)

print(f"\n🌱 Crop")
print(f"   {result['crop']}")

print(f"\n🔬 Diagnosis")
print(f"   {result['diagnosis']}")

print(f"\n🎯 Confidence")
print(f"   {result['confidence']:.2f}%")

print(f"\n⚠️ Severity")
print(f"   {result['severity']}")

print(f"\n🩺 Symptoms")
print(f"   {result['symptoms']}")

print(f"\n🛡️ Preventive Measures")

for measure in result["prevention"]:
    print(f"   • {measure}")

print(f"\n👨‍🌾 Expert Review")
print(
    "   Recommended"
    if result["expert_review"]
    else "   Not required"
)

print("\n" + "=" * 50)