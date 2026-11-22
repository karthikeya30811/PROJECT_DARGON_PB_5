"""Document checklist and steps for a scheme. Tracker/reminders are not implemented here."""


def build_checklist(scheme):
    """Return documents (unchecked), numbered steps, where to apply and terms."""
    documents = [
        {"label": str(doc), "checked": False}
        for doc in (scheme.get("documents") or [])
    ]
    steps = [
        f"{number}. {step}"
        for number, step in enumerate(scheme.get("steps") or [], start=1)
    ]
    return {
        "documents": documents,
        "steps": steps,
        "where_to_apply": scheme.get("where_to_apply") or None,
        "terms_and_conditions": scheme.get("terms_and_conditions") or None,
    }
