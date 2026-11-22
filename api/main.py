"""FastAPI app: connects the UI to the engine."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, File, Form, HTTPException, UploadFile  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import Response  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from engine.match import analyze, apply_answers, load_schemes  # noqa: E402
from engine.stt import transcribe  # noqa: E402
from reminders.reminders import (  # noqa: E402
    compute_reminders,
    get_entries,
    make_ics,
    save_entry,
)

app = FastAPI(title="Claim What's Yours")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., max_length=2000)
    language: str = "en"


class AnswersRequest(BaseModel):
    profile: dict
    answers: dict


class TrackerEntry(BaseModel):
    user_id: str
    scheme_id: str
    status: str
    application_id: Optional[str] = None
    applied_on: Optional[str] = None


class OutdatedReport(BaseModel):
    scheme_id: str
    note: str = ""


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"status": "ok", "message": "API running. See /docs"}


@app.post("/api/report-outdated")
def report_outdated(report: OutdatedReport):
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    line = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scheme_id": report.scheme_id,
        "note": report.note,
    }
    with (data_dir / "outdated_reports.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return {"status": "received"}


@app.post("/api/analyze")
def analyze_text(req: AnalyzeRequest):
    try:
        return analyze(req.text, language=req.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/answers")
def answers(req: AnswersRequest):
    try:
        merged = apply_answers(req.profile, req.answers)
        return analyze("", profile_overrides=merged)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/schemes/{scheme_id}")
def get_scheme(scheme_id: str):
    for scheme in load_schemes():
        if scheme.get("scheme_id") == scheme_id:
            return scheme
    raise HTTPException(status_code=404, detail=f"unknown scheme_id: {scheme_id}")


@app.post("/api/voice-evaluate")
async def voice_evaluate(
    audio: UploadFile = File(...),
    language: str = Form("en"),
):
    audio_bytes = await audio.read()
    try:
        transcript = transcribe(audio_bytes, language)
    except RuntimeError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    return analyze(transcript, language)


@app.post("/api/tracker")
def tracker_save(entry: TrackerEntry):
    try:
        return save_entry(entry.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/tracker/{user_id}")
def tracker_get(user_id: str):
    try:
        return {
            "entries": get_entries(user_id),
            "reminders": compute_reminders(user_id),
        }
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/reminders/ics")
def reminders_ics(user_id: str):
    try:
        content = make_ics(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return Response(
        content=content,
        media_type="text/calendar",
        headers={"Content-Disposition": 'attachment; filename="reminders.ics"'},
    )
