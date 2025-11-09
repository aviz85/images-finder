# specs.md — Local-only Semantic Image Search (Python + SQLite + FAISS)

## 1) Overview
Build a **fully local**, privacy-preserving semantic search engine over ~**4,000,000 images**.  
Core: generate **image embeddings** with a local open model (e.g., SigLIP-2 / OpenCLIP), index vectors with **FAISS (IVF-PQ)**, store metadata in **SQLite**, and serve queries (text→image and image→image). Optional “quality boosters” (captions, re-ranking, object checks) are layered and switchable.

---

## 2) Goals & Non-Goals
**Goals**
- End-to-end local pipeline: thumbnails → embeddings → index → search.
- Scales to ≈4M images on a single workstation (GPU recommended; CPU-only possible, slower).
- Deterministic, resumable batch jobs with progress tracking.
- Low RAM footprint for search via FAISS IVF-PQ; refined Top-K with exact vectors.
- Clean CLI + optional local HTTP API (FastAPI).

**Non-Goals**
- Cloud services (no external APIs).
- Online learning or vector updates during query time (index updates are batched).
- Perfect object detection/segmentation (only optional verification on Top-K).

---

## 3) High-Level Architecture
(… full content omitted for brevity … see previous messages)
