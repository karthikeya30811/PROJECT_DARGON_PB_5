"""Deadline reminders, tracker state and .ics export."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.match import load_schemes  # noqa: E402

TRACKER_PATH = Path(__file__).resolve().parents[1] / "data" / "tracker.json"
ALLOWED_STATUSES = ["Not Started", "Documents Ready", "Applied", "Follow-up Due", "Completed"]
ALLOWED_KEYS = {"user_id", "scheme_id", "status", "application_id", "applied_on"}
FOLLOW_UP_DAYS = 30
PRODID = "-//Claim Whats Yours//EN"
_USER_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


def load_tracker() -> list:
    """Return all tracker entries; an empty list if the file is missing."""
    if not TRACKER_PATH.exists():
        return []
    with TRACKER_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return list(data) if isinstance(data, list) else []


def save_tracker(entries: list) -> None:
    """Write all tracker entries to disk as JSON."""
    TRACKER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER_PATH.open("w", encoding="utf-8") as fh:
        json.dump(entries, fh, indent=2, ensure_ascii=False)


def _validate_user_id(user_id) -> str:
    if not isinstance(user_id, str) or not user_id:
        raise ValueError("user_id must be a non-empty string")
    if len(user_id) > 64:
        raise ValueError("user_id must be at most 64 characters")
    if not _USER_ID_RE.fullmatch(user_id):
        raise ValueError("user_id may only contain letters, digits, '-' and '_'")
    return user_id


def _coerce_date(value) -> Optional[date]:
    """Best-effort conversion of a scheme or stored date value to a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def _resolve_today(today) -> date:
    if today is None:
        return datetime.now(timezone.utc).date()
    resolved = _coerce_date(today)
    if resolved is None:
        raise ValueError("today must be a date or YYYY-MM-DD string")
    return resolved


def save_entry(entry: dict) -> dict:
    """Validate and upsert one tracker entry keyed by (user_id, scheme_id)."""
    if not isinstance(entry, dict):
        raise ValueError("entry must be an object")
    extra = set(entry) - ALLOWED_KEYS
    if extra:
        raise ValueError(f"unexpected keys: {sorted(extra)}")

    user_id = _validate_user_id(entry.get("user_id"))

    scheme_id = entry.get("scheme_id")
    known_ids = {s.get("scheme_id") for s in load_schemes()}
    if not isinstance(scheme_id, str) or scheme_id not in known_ids:
        raise ValueError(f"unknown scheme_id: {scheme_id!r}")

    status = entry.get("status")
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"status must be one of {ALLOWED_STATUSES}")

    application_id = entry.get("application_id")
    if application_id is not None:
        if not isinstance(application_id, str) or len(application_id) > 64:
            raise ValueError("application_id must be a string of at most 64 characters")

    applied_on = entry.get("applied_on")
    if applied_on is not None:
        if not isinstance(applied_on, str):
            raise ValueError("applied_on must be a YYYY-MM-DD string")
        try:
            datetime.strptime(applied_on, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("applied_on must be a YYYY-MM-DD string") from exc

    record = {
        "user_id": user_id,
        "scheme_id": scheme_id,
        "status": status,
        "application_id": application_id,
        "applied_on": applied_on,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    entries = load_tracker()
    for index, existing in enumerate(entries):
        if existing.get("user_id") == user_id and existing.get("scheme_id") == scheme_id:
            entries[index] = record
            break
    else:
        entries.append(record)
    save_tracker(entries)
    return record


def get_entries(user_id: str) -> list:
    """Return all tracker entries belonging to one user."""
    return [e for e in load_tracker() if e.get("user_id") == user_id]


def compute_reminders(user_id: str, today=None) -> list:
    """Build deadline and follow-up reminders for one user."""
    _validate_user_id(user_id)
    today_d = _resolve_today(today)

    status_by_scheme = {}
    applied_by_scheme = {}
    for entry in get_entries(user_id):
        sid = entry.get("scheme_id")
        status_by_scheme[sid] = entry.get("status")
        applied_by_scheme[sid] = entry.get("applied_on")

    reminders = []
    for scheme in load_schemes():
        sid = scheme.get("scheme_id")
        name = str(scheme.get("name") or sid)
        status = status_by_scheme.get(sid)

        deadline = _coerce_date(scheme.get("deadline_date"))
        if deadline and status != "Completed" and deadline >= today_d:
            reminders.append({
                "scheme_id": sid,
                "name": name,
                "message": f"Deadline {deadline.isoformat()} for {name}",
                "due_date": deadline.isoformat(),
            })

        applied_on = _coerce_date(applied_by_scheme.get(sid))
        if status == "Applied" and applied_on:
            due = applied_on + timedelta(days=FOLLOW_UP_DAYS)
            if due <= today_d:
                reminders.append({
                    "scheme_id": sid,
                    "name": name,
                    "message": f"Follow up on {name} (applied on {applied_on.isoformat()})",
                    "due_date": due.isoformat(),
                })

    reminders.sort(key=lambda r: (r["due_date"], r["scheme_id"]))
    return reminders


def _escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def make_ics(user_id: str, today=None) -> str:
    """Return an RFC 5545 calendar with one all-day event per reminder."""
    _validate_user_id(user_id)
    today_d = _resolve_today(today)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:{PRODID}", "CALSCALE:GREGORIAN"]
    for reminder in compute_reminders(user_id, today=today_d):
        due = datetime.strptime(reminder["due_date"], "%Y-%m-%d").date()
        start = due.strftime("%Y%m%d")
        end = (due + timedelta(days=1)).strftime("%Y%m%d")
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{user_id}-{reminder['scheme_id']}-{reminder['due_date']}@claim-whats-yours",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{end}",
            f"SUMMARY:{_escape_text(reminder['message'])}",
            "END:VEVENT",
        ])
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
