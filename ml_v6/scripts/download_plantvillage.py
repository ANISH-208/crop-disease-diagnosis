from datasets import load_dataset

print("=" * 60)
print("Crop Doctor AI — PlantVillage V6 Download")
print("=" * 60)

dataset = load_dataset("mohanty/PlantVillage")

print("\nDataset downloaded successfully.")
print(dataset)

for split in dataset:
    print(f"{split}: {len(dataset[split])} images")

print("\nFeatures:")
print(dataset["train"].features)

label_feature = dataset["train"].features["label"]

print("\nClass count:")
print(label_feature.num_classes)

print("\nClass names:")
for i, name in enumerate(label_feature.names):
    print(f"{i:02d}  {name}")
