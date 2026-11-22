"""Rules x profile to PASS/UNVERIFIED/FAIL with reasons, plus analyze().

Scheme data is read from data/schemes/*.yaml (project root). Schemes are
loaded once and cached; treat the returned data as read-only.
"""

import re
from functools import lru_cache
from pathlib import Path

import yaml

from engine.checklist import build_checklist
from engine.extract_profile import extract_profile
from engine.guardrails import check_wording, mask_sensitive

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMES_DIR = PROJECT_ROOT / "data" / "schemes"

DISCLAIMER = (
    "This shows likely eligibility based on public information. "
    "It is not a guarantee. Confirm on the official portal."
)
NO_MATCH_NOTE = (
    "No scheme matched your situation strongly. Showing all schemes; check each one."
)
NO_RULES_TEXT = "Eligibility is written as free text. Read the terms and conditions."
NO_RULES_EXPLANATION = "No rule can be checked automatically for this scheme."

VERDICT_ORDER = {"likely_eligible": 0, "possibly_eligible": 1, "needs_verification": 2, "not_eligible": 3}

PROFILE_FIELDS = (
    "state",
    "age",
    "annual_family_income",
    "category",
    "education_level",
    "occupation",
    "land_acres",
    "gender",
    "has_bank_account",
    "has_ration_card",
    "has_disability",
)

CHOICE_FIELDS = {
    "state": ["Andhra Pradesh"],
    "category": ["SC", "ST", "BC", "OC", "EWS", "MINORITY"],
    "education_level": ["primary", "secondary", "intermediate", "graduate", "postgraduate"],
    "occupation": [
        "student",
        "farmer",
        "daily_wage",
        "auto_driver",
        "self_employed",
        "salaried",
        "unemployed",
        "homemaker",
        "retired",
        "other",
    ],
    "gender": ["female", "male", "other"],
}

# field -> (question, kind, options)
QUESTION_TEXT = {
    "age": ("What is your age?", "number", None),
    "annual_family_income": ("What is your annual family income?", "number", None),
    "category": (
        "Which category do you belong to: SC, ST, BC, OC, EWS or minority?",
        "choice",
        CHOICE_FIELDS["category"],
    ),
    "education_level": ("What is your education level?", "choice", CHOICE_FIELDS["education_level"]),
    "occupation": ("What is your main occupation?", "choice", CHOICE_FIELDS["occupation"]),
    "land_acres": ("Do you own agricultural land? How many acres?", "number", None),
    "has_bank_account": ("Do you have a bank account?", "bool", None),
    "has_ration_card": ("Do you have a ration card?", "bool", None),
    "has_disability": ("Do you have a disability certificate (any percentage)?", "bool", None),
    "gender": ("Are you a woman?", "bool", None),
    "state": ("Which state do you live in?", "choice", CHOICE_FIELDS["state"]),
}

# Keyword groups: a group counts toward relevance when the user's text uses one
# of its words and the scheme fits the group (see relevance()).
KEYWORD_GROUPS = {
    "education": {
        "words": ["student", "school", "college", "scholarship", "fees", "study",
                  "class", "degree", "bsc", "education"],
        "categories": ["education"],
    },
    "agriculture": {
        "words": ["farmer", "farm", "crop", "rythu", "agriculture", "seeds", "land"],
        "categories": ["agriculture"],
    },
    "pension": {
        "words": ["pension", "old age", "elderly", "senior", "retired"],
        "categories": ["pension"],
    },
    "health": {
        "words": ["health", "hospital", "medical", "insurance", "treatment", "sick"],
        "categories": ["health"],
    },
    "housing": {
        "words": ["house", "housing", "home", "shelter", "roof"],
        "categories": ["housing"],
    },
    "travel": {
        "words": ["bus", "travel", "commute", "apsrtc", "work", "job", "training"],
        "categories": ["livelihood"],
    },
    "women": {
        "words": ["woman", "women", "mother", "girl", "widow", "mahila"],
        "categories": ["women"],
    },
    "livelihood": {
        "words": ["business", "loan", "enterprise", "self employed", "self-employed",
                  "shop", "income", "daily wage", "job"],
        "categories": ["livelihood"],
    },
}


@lru_cache(maxsize=1)
def load_schemes():
    """Load every data/schemes/*.yaml file. Cached; do not mutate the result."""
    schemes = []
    for path in sorted(SCHEMES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if isinstance(data, dict):
            schemes.append(data)
    return schemes


def _has_word(text, word):
    return re.search(r"\b" + re.escape(word) + r"\b", text) is not None


def relevance(scheme, text_lower, profile=None):
    """Count the keyword groups that make this scheme relevant to the user.

    Rule: a group scores 1 when
      (a) any of its words appears in the user's text, AND
      (b) the scheme's category is in the group's categories, OR any of its
          words appears in the scheme's name or when_it_may_help.
    The score is the number of groups that score. `profile` is accepted for
    the calling convention but relevance is driven by the user's text only.
    """
    scheme_text = " ".join(
        str(scheme.get(key) or "") for key in ("name", "when_it_may_help")
    ).lower()
    category = scheme.get("category")
    score = 0
    for group in KEYWORD_GROUPS.values():
        if not any(_has_word(text_lower, word) for word in group["words"]):
            continue
        in_categories = category in group["categories"]
        in_scheme_text = any(_has_word(scheme_text, word) for word in group["words"])
        if in_categories or in_scheme_text:
            score += 1
    return score


def _not_eligible_by_rule(rule_id, text, field, op, value, actual_text):
    return {
        "rule_id": rule_id,
        "text": text,
        "result": "FAIL",
        "explanation": f"Your {field} is {actual_text} but the rule needs {op} {value}.",
    }


def _evaluate_group(rule, profile):
    """Evaluate an all_of / any_of group. Returns {rule_id, text, result, explanation}."""
    rule_id = rule.get("id")
    text = rule.get("text") or ""
    is_all = "all_of" in rule
    children = (rule.get("all_of") if is_all else rule.get("any_of")) or []
    reasons = [evaluate_rule(child, profile) for child in children]
    results = {reason["result"] for reason in reasons}
    if is_all:
        if "FAIL" in results:
            result = "FAIL"
        elif results == {"PASS"}:
            result = "PASS"
        else:
            result = "UNVERIFIED"
    else:
        if "PASS" in results:
            result = "PASS"
        elif reasons and results == {"FAIL"}:
            result = "FAIL"
        else:
            result = "UNVERIFIED"
    explanation = " ; ".join(reason["explanation"] for reason in reasons)
    return {"rule_id": rule_id, "text": text, "result": result, "explanation": explanation}


def evaluate_rule(rule, profile):
    """Check one rule against the profile. Returns {rule_id, text, result, explanation}.

    A rule may also be a group: {"id", "all_of": [...]} or {"id", "any_of": [...]}.
    """
    if "all_of" in rule or "any_of" in rule:
        return _evaluate_group(rule, profile)
    rule_id = rule.get("id")
    text = rule.get("text")
    field = rule.get("field")
    op = rule.get("op")
    value = rule.get("value")
    base = {"rule_id": rule_id, "text": text}

    # A state rule that names "All India" applies everywhere, so it does not
    # need the user's state.
    if field == "state" and value == "All India":
        return {**base, "result": "PASS", "explanation": "This scheme applies across India."}

    if profile.get(field) is None:
        return {**base, "result": "UNVERIFIED",
                "explanation": f"We do not know your {field} yet."}

    actual = profile[field]
    try:
        if op == "<=":
            ok = actual <= value
        elif op == ">=":
            ok = actual >= value
        elif op == "==":
            ok = actual == value
        elif op == "!=":
            ok = actual != value
        elif op == "in":
            ok = actual in (value or [])
        elif op == "not_in":
            ok = actual not in (value or [])
        elif op == "bool":
            ok = actual == value
        else:
            return {**base, "result": "UNVERIFIED",
                    "explanation": f"This rule uses a check ({op}) that is not supported yet."}
    except TypeError:
        return {**base, "result": "UNVERIFIED",
                "explanation": f"We cannot compare your {field} with this rule yet."}

    if ok:
        return {**base, "result": "PASS", "explanation": f"Your {field} is {actual}."}
    return _not_eligible_by_rule(rule_id, text, field, op, value, actual)


def scheme_verdict(scheme, profile):
    """Return (verdict, reasons) for one scheme.

    No rules -> needs_verification. Any FAIL -> not_eligible.
    Any UNVERIFIED -> possibly_eligible. All PASS -> possibly_eligible if the scheme
    has unresolved_conditions (with an extra reason listing them), else likely_eligible.
    """
    rules = scheme.get("rules") or []
    if not rules:
        return "needs_verification", [{
            "rule_id": "no_machine_rules",
            "text": NO_RULES_TEXT,
            "result": "UNVERIFIED",
            "explanation": NO_RULES_EXPLANATION,
        }]

    reasons = [evaluate_rule(rule, profile) for rule in rules]
    results = {reason["result"] for reason in reasons}
    if "FAIL" in results:
        return "not_eligible", reasons
    if "UNVERIFIED" in results:
        return "possibly_eligible", reasons
    unresolved = list(scheme.get("unresolved_conditions") or [])
    if unresolved:
        reasons.append({
            "rule_id": "unresolved_conditions",
            "text": "Some conditions could not be checked automatically.",
            "result": "UNVERIFIED",
            "explanation": "Please confirm: " + "; ".join(str(item) for item in unresolved),
        })
        return "possibly_eligible", reasons
    return "likely_eligible", reasons


def _rule_fields(rule):
    """Yield the profile field of a rule, walking into all_of / any_of children."""
    if "all_of" in rule or "any_of" in rule:
        for child in (rule.get("all_of") or []) + (rule.get("any_of") or []):
            yield from _rule_fields(child)
    elif rule.get("field"):
        yield rule["field"]


def missing_fields(schemes):
    """Return the set of profile fields used by any rule in these schemes."""
    fields = set()
    for scheme in schemes:
        for rule in scheme.get("rules") or []:
            fields.update(_rule_fields(rule))
    return fields


def _to_number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.replace(",", "").strip())
        except ValueError:
            return None
    return None


def _clean_value(field, value):
    """Return the cleaned value for a profile field, or None if invalid."""
    if field == "gender" and isinstance(value, bool):
        return "female" if value else "male"
    if field in CHOICE_FIELDS:
        if not isinstance(value, str):
            return None
        for option in CHOICE_FIELDS[field]:
            if value.strip().lower() == option.lower():
                return option
        return None
    if field == "age":
        number = _to_number(value)
        if number is None or not 1 <= round(number) <= 110:
            return None
        return int(round(number))
    if field == "annual_family_income":
        number = _to_number(value)
        if number is None or round(number) < 0:
            return None
        return int(round(number))
    if field == "land_acres":
        number = _to_number(value)
        if number is None or number < 0:
            return None
        return number
    if field in ("has_bank_account", "has_ration_card", "has_disability"):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("yes", "true"):
                return True
            if lowered in ("no", "false"):
                return False
        return None
    return None


def _validate_fields(values):
    """Return (clean_dict, warnings). Unknown keys and invalid values are dropped."""
    clean = {}
    warnings = []
    for key, value in values.items():
        if value is None:
            continue
        if key not in PROFILE_FIELDS:
            warnings.append(f"Ignored unknown field '{key}'.")
            continue
        cleaned = _clean_value(key, value)
        if cleaned is None:
            warnings.append(f"Ignored invalid value for {key}: {value!r}.")
            continue
        clean[key] = cleaned
    return clean, warnings


def apply_answers(profile, answers):
    """Return profile merged with validated answers. Raises ValueError if any answer is rejected."""
    clean, warnings = _validate_fields(answers or {})
    if warnings:
        raise ValueError(" ".join(warnings))
    merged = dict(profile or {})
    merged.update(clean)
    return merged


def _question_for(field):
    question, kind, options = QUESTION_TEXT[field]
    return {"field": field, "question": question, "kind": kind, "options": options}


def _scheme_result(scheme, relevance_score, verdict, reasons):
    return {
        "scheme_id": scheme.get("scheme_id"),
        "name": scheme.get("name"),
        "level": scheme.get("level"),
        "state": scheme.get("state"),
        "category": scheme.get("category"),
        "benefit": scheme.get("benefit"),
        "official_source": scheme.get("official_source"),
        "last_verified": scheme.get("last_verified"),
        "rule_conversion_status": scheme.get("rule_conversion_status"),
        "manual_verification_required": bool(scheme.get("manual_verification_required")),
        "unresolved_conditions": list(scheme.get("unresolved_conditions") or []),
        "verdict": verdict,
        "relevance": relevance_score,
        "reasons": reasons,
        "documents": scheme.get("documents") or [],
        "steps": scheme.get("steps") or [],
        "deadline": scheme.get("deadline"),
        "deadline_date": scheme.get("deadline_date"),
        "context": {
            "where_to_apply": scheme.get("where_to_apply"),
            "terms_and_conditions": scheme.get("terms_and_conditions"),
            "does_not_provide": scheme.get("does_not_provide"),
            "when_it_may_help": scheme.get("when_it_may_help"),
        },
        "checklist": build_checklist(scheme),
    }


def _collect_generated_strings(output):
    """Strings the engine itself writes. Scheme-authored text is excluded:
    the source data may quote terms such as "not a guaranteed job" in
    does_not_provide, and that is the official wording, not an engine claim."""
    generated = [output["disclaimer"], output["selection_note"]]
    generated.extend(output["warnings"])
    generated.extend(q["question"] for q in output["questions"])
    for result in output["results"]:
        generated.extend(reason["explanation"] for reason in result["reasons"])
    for item in output["not_matching"]:
        generated.extend(reason["explanation"] for reason in item["reasons"])
    return [text for text in generated if text]


def analyze(text, language="en", profile_overrides=None):
    """Turn a plain-language situation into scheme results and follow-up questions."""
    masked, _ = mask_sensitive(text or "")
    text_lower = masked.lower()

    extracted = extract_profile(text or "", language)
    profile = dict(extracted["profile"])
    warnings = list(extracted["warnings"])
    overrides, override_warnings = _validate_fields(profile_overrides or {})
    profile.update(overrides)
    warnings.extend(override_warnings)

    candidates = []  # relevance > 0, not not_eligible
    fallback = []    # relevance == 0, not not_eligible
    not_matching = []
    for scheme in load_schemes():
        rel = relevance(scheme, text_lower, profile)
        verdict, reasons = scheme_verdict(scheme, profile)
        result = _scheme_result(scheme, rel, verdict, reasons)
        if rel > 0 and verdict == "not_eligible":
            not_matching.append({
                "scheme_id": scheme.get("scheme_id"),
                "name": scheme.get("name"),
                "reasons": [r for r in reasons if r["result"] == "FAIL"],
            })
        elif rel > 0:
            candidates.append((scheme, result))
        elif verdict != "not_eligible":
            fallback.append((scheme, result))

    if candidates:
        chosen = candidates
        selection_note = ""
    else:
        chosen = fallback
        selection_note = NO_MATCH_NOTE

    chosen.sort(key=lambda pair: (-pair[1]["relevance"], VERDICT_ORDER[pair[1]["verdict"]]))
    results = [result for _, result in chosen]

    seen = set()
    missing = []
    for scheme, _ in chosen:
        for rule in scheme.get("rules") or []:
            field = rule.get("field")
            if not field or field in seen or field in profile:
                continue
            if field == "state" and rule.get("value") == "All India":
                continue
            seen.add(field)
            missing.append(field)
    questions = [_question_for(field) for field in missing]

    output = {
        "profile": profile,
        "warnings": warnings,
        "missing_fields": missing,
        "questions": questions,
        "results": results,
        "not_matching": not_matching,
        "selection_note": selection_note,
        "disclaimer": DISCLAIMER,
    }

    violations = check_wording(_collect_generated_strings(output))
    if violations:
        raise ValueError("; ".join(violations))
    return output
