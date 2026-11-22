"""Offline tests for the matching engine, guardrails, reminders and API."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.extract_profile import extract_profile  # noqa: E402
from engine.guardrails import mask_sensitive  # noqa: E402
from engine.match import analyze, load_schemes  # noqa: E402
from reminders import reminders as reminders_mod  # noqa: E402
from reminders.reminders import make_ics, save_entry  # noqa: E402

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_profiles"
CONTEXT_KEYS = {"where_to_apply", "terms_and_conditions", "does_not_provide", "when_it_may_help"}


def _sample_texts():
    return [
        (path.name, json.loads(path.read_text(encoding="utf-8"))["text"])
        for path in sorted(SAMPLE_DIR.glob("*.json"))
    ]


def test_masks_aadhaar_and_pan():
    masked, _found = mask_sensitive("Aadhaar 1234 5678 9012 and PAN ABCDE1234F")
    assert "[masked]" in masked
    assert "1234 5678 9012" not in masked


def test_extracts_student_profile():
    profile = extract_profile(
        "I am 17, I study in class 11 in a govt school, we earn about 1.8 lakh a year, Andhra Pradesh"
    )["profile"]
    assert profile["age"] == 17
    assert profile["annual_family_income"] == 180000
    assert profile["education_level"] == "intermediate"
    assert profile["state"] == "Andhra Pradesh"


@pytest.mark.parametrize("name,text", _sample_texts())
def test_sample_profiles_run(name, text):
    output = analyze(text)
    assert "results" in output, name
    assert "disclaimer" in output, name
    for result in output["results"]:
        assert "context" in result, name
        assert CONTEXT_KEYS <= set(result["context"]), name


@pytest.mark.parametrize("name,text", _sample_texts())
def test_no_guaranteed_wording(name, text):
    output = analyze(text)
    for field in ("disclaimer", "selection_note"):
        assert "guaranteed" not in str(output.get(field) or "").lower(), (name, field)


def test_missing_field_is_unverified():
    output = analyze("I am 17 in Andhra Pradesh")
    for result in output["results"]:
        for reason in result.get("reasons", []):
            if "do not know" in str(reason.get("explanation", "")):
                assert reason.get("result") == "UNVERIFIED"


def test_zero_rule_scheme_never_likely():
    zero_rule_ids = {
        s.get("scheme_id") for s in load_schemes() if not s.get("rules")
    }
    output = analyze("I am 17 in Andhra Pradesh")
    for result in output["results"]:
        sid = result.get("scheme_id")
        if sid in zero_rule_ids:
            assert result.get("verdict") != "likely_eligible", sid


def test_tracker_rejects_bad_status(tmp_path, monkeypatch):
    monkeypatch.setattr(reminders_mod, "TRACKER_PATH", tmp_path / "tracker.json")
    first_scheme = load_schemes()[0]["scheme_id"]
    with pytest.raises(ValueError):
        save_entry({"user_id": "u1", "scheme_id": first_scheme, "status": "Done"})


def test_ics_format(tmp_path, monkeypatch):
    monkeypatch.setattr(reminders_mod, "TRACKER_PATH", tmp_path / "tracker.json")
    ics = make_ics("test_user")
    assert ics.startswith("BEGIN:VCALENDAR")
    assert "\r\n" in ics
    assert ics.endswith("END:VCALENDAR\r\n")


def test_api_health():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}
