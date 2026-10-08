# Crop Doctor AI

> AI-powered crop disease diagnosis and real-time agricultural alert system.

Crop Doctor AI is an intelligent agriculture diagnostic platform that analyzes crop leaf images using a deep-learning vision model, identifies the most likely disease, provides preventive recommendations, and streams diagnostic events to an expert-review workflow in real time.

---

## Overview

Crop Doctor AI combines:

- Deep-learning image classification
- 38-class crop disease recognition
- EfficientNetV2-S
- FastAPI backend
- React + Vite frontend
- WebSocket-based realtime events
- SQLite alert persistence
- Expert escalation workflow
- Confidence and top-prediction telemetry

The system is designed as a diagnostic-assistance platform and is **not a replacement for professional agricultural expertise**.

---

## System Architecture

```text
                         ┌──────────────────────┐
                         │     React Frontend   │
                         │     Crop Doctor AI   │
                         └──────────┬───────────┘
                                    │
                         HTTP / REST API
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │     FastAPI Backend   │
                         │                      │
                         │  /diagnose           │
                         │  /alerts             │
                         │  /health             │
                         │  /ws                 │
                         └──────────┬───────────┘
                                    │
                         Image preprocessing
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    EfficientNetV2-S  │
                         │                      │
                         │      38 Classes      │
                         └──────────┬───────────┘
                                    │
                              Prediction
                                    │
                   ┌────────────────┴────────────────┐
                   ▼                                 ▼
          ┌──────────────────┐             ┌──────────────────┐
          │ Disease Metadata │             │  SQLite Alerts   │
          │ & Prevention     │             │   Persistence    │
          └────────┬─────────┘             └────────┬─────────┘
                   │                                 │
                   └────────────────┬────────────────┘
                                    │
                              WebSocket Events
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │ Realtime Dashboard   │
                         │                      │
                         │ Diagnosis            │
                         │ Confidence           │
                         │ Event Stream         │
                         │ Expert Center        │
                         └──────────────────────┘
