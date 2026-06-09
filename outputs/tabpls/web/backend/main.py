"""
TabPls FastAPI backend.

Endpoints:
  POST /transcribe  — Upload an audio file, receive ASCII tab
  GET  /health      — Liveness check

Run locally:
  cd web/backend
  pip install -r requirements.txt
  uvicorn main:app --reload --port 8000

For GPU inference on Modal.com, see the deploy/ directory (Phase 3).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# src/ lives two levels up from web/backend/
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

import fretboard as _fb
import pipeline as _pipeline

app = FastAPI(
    title="TabPls API",
    version="0.2.0",
    description="Guitar audio → ASCII tab transcription service",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_TUNINGS = list(_fb.TUNINGS.keys())
MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/tunings")
def tunings():
    """Return available guitar tunings."""
    return {"tunings": VALID_TUNINGS}


@app.post("/transcribe", response_class=PlainTextResponse)
async def transcribe(
    audio: UploadFile = File(..., description="Guitar audio file (.mp3, .wav, .flac, .ogg)"),
    tuning: str = Form(default="standard", description="Guitar tuning"),
    bpm: float = Form(default=120.0, ge=20.0, le=300.0, description="Song tempo (BPM)"),
    separate: bool = Form(default=False, description="Run Demucs source separation"),
    compact: bool = Form(default=False, description="Compact non-quantized rendering"),
    onset_threshold: float = Form(default=0.50, ge=0.1, le=0.95, description="Note detection sensitivity"),
    detect_techniques: bool = Form(default=True, description="Annotate h/p/b/~ techniques"),
):
    """
    Transcribe an uploaded guitar audio file to ASCII tab.

    Returns plain-text ASCII tab. Errors return JSON with a 'detail' field.
    """
    if tuning not in VALID_TUNINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tuning '{tuning}'. Valid options: {VALID_TUNINGS}",
        )

    content = await audio.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // 1024 // 1024} MB). Maximum is {MAX_UPLOAD_MB} MB.",
        )

    suffix = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
    allowed = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. Supported: {sorted(allowed)}",
        )

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(content)

    try:
        tab = _pipeline.transcribe(
            tmp_path,
            tuning=tuning,
            bpm=bpm,
            separate=separate,
            compact=compact,
            onset_threshold=onset_threshold,
            detect_techniques=detect_techniques,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    return tab
