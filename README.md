# 🌱 Crop Doctor AI

### AI-Powered Crop Disease Diagnosis & Real-Time Agricultural Alert System

Crop Doctor AI is an end-to-end machine learning application that analyzes crop leaf images, predicts potential diseases, provides crop-health information and preventive measures, and connects high-priority cases to an agricultural expert alert workflow.

The system combines a fine-tuned **EfficientNetV2-S** image classification model with a **FastAPI backend**, **React frontend**, persistent alert management, and **WebSocket-based real-time updates**.

---

## 🚀 Key Features

- 🌿 **AI crop disease diagnosis** from uploaded leaf images
- 🧠 **EfficientNetV2-S** image classification model
- 🔬 **38-class PlantVillage disease taxonomy**
- 📊 **99.04% test accuracy** on the held-out PlantVillage benchmark
- 🎯 **99.98% Top-5 accuracy**
- 📈 **98.58% Macro F1**
- 🩺 Disease symptoms and preventive recommendations
- 🚨 Automatic expert-review alerts
- ⚡ Real-time diagnosis and alert events through WebSockets
- 💾 SQLite-backed alert persistence
- 🖥️ Interactive React dashboard
- 🔌 REST API for diagnosis and alert management
- 📦 Model versioning and Git LFS support

> **Important:** The reported ML metrics are PlantVillage benchmark results. They should not be interpreted as real-world field accuracy.

---

# 🏗️ System Architecture

```text
                         ┌─────────────────────────┐
                         │      Crop Image         │
                         │     JPG / PNG           │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │    React Frontend       │
                         │      Crop Doctor AI     │
                         └────────────┬────────────┘
                                      │
                              HTTP / WebSocket
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │     FastAPI Backend      │
                         │                         │
                         │  /diagnose              │
                         │  /alerts                │
                         │  /ws                    │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   EfficientNetV2-S       │
                         │                         │
                         │   224 × 224 RGB         │
                         │   38 disease classes    │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   Diagnosis Pipeline    │
                         │                         │
                         │ Crop                    │
                         │ Disease                 │
                         │ Confidence              │
                         │ Severity                │
                         │ Prevention              │
                         │ Expert Review           │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │     Alert System        │
                         │                         │
                         │ Pending                 │
                         │ In Review               │
                         │ Resolved                │
                         └─────────────────────────┘
