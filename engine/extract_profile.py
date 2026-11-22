"""Plain text to structured profile fields. Rule-based and offline.

Keyword and regex matching across English, Telugu and Hindi terms. The
`language` argument is accepted for the API but does not change matching.
Only fields that are found are returned; missing fields are not computed here.
"""

import re

from engine.guardrails import mask_sensitive

SENSITIVE_WARNING = (
    "Sensitive numbers were removed from your text. "
    "Do not enter Aadhaar, PAN or bank details."
)

STATE_PATTERN = re.compile(r"andhra|\bap\b|ఆంధ్ర|आंध्र")

AGE_PATTERNS = [
    re.compile(r"\bi am (\d{1,2})\b"),
    re.compile(r"\b(\d{1,2}) years? old\b"),
    re.compile(r"\bage (\d{1,2})\b"),
    re.compile(r"\b(\d{1,2}) saal\b"),
    re.compile(r"(\d{1,2})\s*ఏళ్ళ"),
]

LAKH_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:lakhs?|lacs?)\b")
# Plain rupee amounts: "50000" or Indian comma grouping "1,50,000".
RUPEE_PATTERN = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{2,3})+|\d{4,8})(?![\d,])")
INCOME_KEYWORD_PATTERN = re.compile(r"income|earn|salary|per year|annual")
# A number directly followed by these is not a rupee amount.
NOT_RUPEE_FOLLOWER = re.compile(r"\s*(?:acre|year|yr|%|month|day)")
INCOME_WINDOW_CHARS = 40

# Ordered: the highest level wins when several match.
EDUCATION_RULES = [
    (
        re.compile(
            r"\bm\.?sc\b|\bm\.?tech\b|\bm\.?a\b|\bm\.?com\b|postgraduat|masters"
        ),
        "postgraduate",
    ),
    (
        re.compile(
            r"\bb\.?sc\b|\bb\.?tech\b|\bb\.?com\b|\bb\.?a\b|degree|graduat"
        ),
        "graduate",
    ),
    (
        re.compile(r"\bclass (?:11|12)\b|intermediate|inter 1st|inter 2nd"),
        "intermediate",
    ),
    (re.compile(r"\bclass (?:6|7|8|9|10)\b"), "secondary"),
]

# Ordered: first match wins.
OCCUPATION_RULES = [
    (re.compile(r"farmer|farm|rythu|రైతు|किसान"), "farmer"),
    (re.compile(r"\bauto\b|autodriver|auto driver|ఆటో|ऑटो"), "auto_driver"),
    (re.compile(r"daily wage|coolie|labour|labor|construction work"), "daily_wage"),
    (re.compile(r"housewife|homemaker|house wife"), "homemaker"),
    (re.compile(r"retired|pensioner"), "retired"),
    (re.compile(r"self employed|self-employed|own business|shop"), "self_employed"),
    (re.compile(r"salaried|salary job|employee"), "salaried"),
    (re.compile(r"student|study|studying|chaduvu|విద్యార్థి|छात्र"), "student"),
]

# Ordered: first match wins. The lookbehind stops "b.sc" from reading as SC.
CATEGORY_RULES = [
    (re.compile(r"(?<![\w.])sc\b|scheduled caste"), "SC"),
    (re.compile(r"(?<![\w.])st\b|scheduled tribe"), "ST"),
    (re.compile(r"(?<![\w.])bc\b|backward class"), "BC"),
    (re.compile(r"(?<![\w.])ocd?\b|open category|forward caste"), "OC"),
    (re.compile(r"\bews\b"), "EWS"),
    (re.compile(r"minority|muslim|christian"), "MINORITY"),
]

FEMALE_PATTERN = re.compile(
    r"woman|women|female|girl|mother|wife|widow|mahila|మహిళ|महिला"
)
MALE_PATTERN = re.compile(r"\bman\b|\bmale\b|\bboy\b")

LAND_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*acres?\b")

NO_BANK_PATTERN = re.compile(
    r"no bank account|(?:don'?t|do not|dont) have a bank account"
    r"|without a bank account|bank account no\b"
)
HAS_BANK_PATTERN = re.compile(r"have a bank account|bank account yes")

RATION_CARD_PATTERN = re.compile(r"ration card|rice card")
NO_RATION_CARD_PATTERN = re.compile(
    r"\bno (?:ration|rice) card|without (?:a )?(?:ration|rice) card"
    r"|(?:don'?t|do not|dont) have a (?:ration|rice) card"
)

DISABILITY_PATTERN = re.compile(r"disabled|disability|handicap")
NO_DISABILITY_PATTERN = re.compile(
    r"\bno disability|without (?:a )?disability|\bnot disabled"
    r"|(?:don'?t|do not|dont) have a disability"
)


def _find_state(lowered):
    if STATE_PATTERN.search(lowered):
        return "Andhra Pradesh"
    return None


def _find_age(lowered):
    for pattern in AGE_PATTERNS:
        for match in pattern.finditer(lowered):
            age = int(match.group(1))
            if 1 <= age <= 110:
                return age
    return None


def _find_income(lowered):
    for match in LAKH_PATTERN.finditer(lowered):
        return round(float(match.group(1)) * 100000)

    keywords = [m.start() for m in INCOME_KEYWORD_PATTERN.finditer(lowered)]
    if not keywords:
        return None
    for match in RUPEE_PATTERN.finditer(lowered):
        number_start = match.start(1)
        if not any(abs(keyword - number_start) <= INCOME_WINDOW_CHARS for keyword in keywords):
            continue
        if NOT_RUPEE_FOLLOWER.match(lowered, match.end(1)):
            continue
        return int(match.group(1).replace(",", ""))
    return None


def _find_education(lowered):
    for pattern, level in EDUCATION_RULES:
        if pattern.search(lowered):
            return level
    return None


def _find_occupation(lowered):
    for pattern, occupation in OCCUPATION_RULES:
        if pattern.search(lowered):
            return occupation
    return None


def _find_category(lowered):
    for pattern, category in CATEGORY_RULES:
        if pattern.search(lowered):
            return category
    return None


def _find_gender(lowered):
    female = FEMALE_PATTERN.search(lowered) is not None
    male = MALE_PATTERN.search(lowered) is not None
    if female and not male:
        return "female"
    if male and not female:
        return "male"
    return None


def _find_land(lowered):
    match = LAND_PATTERN.search(lowered)
    if match:
        return float(match.group(1))
    return None


def _find_bank(lowered):
    if NO_BANK_PATTERN.search(lowered):
        return False
    if HAS_BANK_PATTERN.search(lowered):
        return True
    return None


def _find_ration_card(lowered):
    if NO_RATION_CARD_PATTERN.search(lowered):
        return False
    if RATION_CARD_PATTERN.search(lowered):
        return True
    return None


def _find_disability(lowered):
    if NO_DISABILITY_PATTERN.search(lowered):
        return False
    if DISABILITY_PATTERN.search(lowered):
        return True
    return None


def extract_profile(text, language="en"):
    """Return {"profile": dict, "warnings": list} from free text.

    Only fields that could be found are included in "profile".
    """
    masked, found_types = mask_sensitive(text or "")
    warnings = []
    if found_types:
        warnings.append(SENSITIVE_WARNING)

    lowered = masked.lower()
    profile = {}

    finders = [
        ("state", _find_state),
        ("age", _find_age),
        ("annual_family_income", _find_income),
        ("education_level", _find_education),
        ("occupation", _find_occupation),
        ("category", _find_category),
        ("gender", _find_gender),
        ("land_acres", _find_land),
        ("has_bank_account", _find_bank),
        ("has_ration_card", _find_ration_card),
        ("has_disability", _find_disability),
    ]
    for field, finder in finders:
        value = finder(lowered)
        if value is not None:
            profile[field] = value

    return {"profile": profile, "warnings": warnings}
