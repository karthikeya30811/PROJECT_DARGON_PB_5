#!/usr/bin/env python3
"""Extract AP scheme data from the Excel workbook into data/schemes/*.yaml.

Stdlib only. Run from the project root:  python scripts/extract_schemes.py
Writes data/schemes/<scheme_id>.yaml and data/verification_log.csv, then validates.
Exit code 1 if any validation check fails.
"""
import csv
import datetime as dt
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
XLSX_NAME = "AP_Government_Schemes_Eligibility_Documents_2026 .xlsx"
SCHEMES_DIR = ROOT / "data" / "schemes"
LOG_PATH = ROOT / "data" / "verification_log.csv"
OVERRIDES_PATH = ROOT / "data" / "rule_overrides.yaml"
OVERRIDE_SOURCE = "; curated rules: data/rule_overrides.yaml"
VERIFIED_BY = "dataset: AP_Government_Schemes_Eligibility_Documents_2026.xlsx"

STATUS_HEADER = "status_as_of_2026-11-21"
EXPECTED_HEADERS = [
    "scheme_name",
    "funding_level",
    "category",
    STATUS_HEADER,
    "benefit",
    "eligibility_criteria",
    "required_documents_typical",
    "official_or_reference_url",
    "where_how_to_apply",
    "terms_and_conditions",
    "what_it_does_not_provide",
    "when_this_scheme_may_help",
]
KEYS = [
    "scheme_id", "name", "level", "state", "category", "benefit",
    "official_source", "last_verified", "verified_by", "criteria_text",
    "rules", "documents", "steps", "deadline", "deadline_date", "notes",
    "where_to_apply", "terms_and_conditions", "does_not_provide", "when_it_may_help",
    "rule_conversion_status", "eligibility_source", "unresolved_conditions",
    "manual_verification_required",
]
ALLOWED_FIELDS = {
    "state", "age", "annual_family_income", "category", "education_level",
    "occupation", "land_acres", "gender", "has_bank_account",
    "has_ration_card", "has_disability",
}
ALLOWED_OPS = {"<=", ">=", "==", "in", "bool"}

CATEGORY_RULES = [
    ("education", r"educat|scholar|student|school|college"),
    ("pension", r"pension|old age|elderly"),
    ("health", r"health|medical|insurance"),
    ("housing", r"housing|house|shelter"),
    ("agriculture", r"agri|farm|crop|fisher|animal"),
    ("livelihood", r"livelihood|employment|self-employment|skill|loan|enterprise"),
    ("women", r"women|girl|widow|mahila"),
]

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

INCOME_CMP = r"(below|less than|under|upto|up to|not exceed|maximum|max|at most|<=)"
INCOME_LAKH = re.compile(
    r"(income|earning)[^.;]*?" + INCOME_CMP + r"[^\d]*(\d[\d,\.]*)\s*(lakhs?|lacs?|l)\b")
INCOME_RUPEE = re.compile(
    r"(income|earning)[^.;]*?" + INCOME_CMP
    + r"\s*(?:rs\.?|₹|inr)?\s*(\d[\d,]*)(?!\s*(?:lakhs?|lacs?|l)\b)")
AGE_RANGE = re.compile(r"\bage\b[^.;]*?(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})")
AGE_MIN = re.compile(r"(?:above|over|minimum|at least)\s*(\d{1,2})")
AGE_MAX = re.compile(r"(?:below|under|upto|up to|maximum)\s*(\d{1,2})")
STATE_RE = re.compile(
    r"resident of andhra pradesh|resident of ap\b|andhra pradesh resident|domicile of andhra")
CAT_PATTERNS = [
    ("SC", r"\bsc\b|scheduled caste"),
    ("ST", r"\bst\b|scheduled tribe"),
    ("BC", r"\bbc\b|backward class"),
    ("OC", r"\boc\b"),
    ("EWS", r"\bews\b"),
    ("MINORITY", r"minority"),
]
GENDER_RE = re.compile(r"\b(women|woman|female|females|girls?)\b")
LAND_RE = re.compile(r"(\d+(?:\.\d+)?)\s*acres?")
DEADLINE_RE = re.compile(r"last date|deadline|\bbefore\b")


# ---------- XLSX reading (stdlib zip + XML) ----------

def local(tag):
    return tag.rsplit("}", 1)[-1]


def col_index(ref):
    letters = re.match(r"[A-Z]+", ref.upper()).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def si_text(el):
    parts = []
    for child in el:
        if local(child.tag) == "t":
            parts.append(child.text or "")
        elif local(child.tag) == "r":  # rich-text run; skip phonetic (rPh)
            for t in child:
                if local(t.tag) == "t":
                    parts.append(t.text or "")
    return "".join(parts)


def cell_value(c, shared):
    t = c.get("t", "")
    if t == "inlineStr":
        is_el = next((x for x in c if local(x.tag) == "is"), None)
        return si_text(is_el) if is_el is not None else ""
    v_el = next((x for x in c if local(x.tag) == "v"), None)
    v = (v_el.text or "") if v_el is not None else ""
    if t == "s":
        try:
            return shared[int(v)]
        except (ValueError, IndexError):
            return ""
    if t == "b":
        return "TRUE" if v.strip() == "1" else "FALSE"
    return v


def find_xlsx():
    p = ROOT / XLSX_NAME
    if p.exists():
        return p
    alt = sorted(ROOT.glob("AP_Government*.xlsx"))
    if alt:
        print(f"NOTE: exact file name not found, using {alt[0].name}")
        return alt[0]
    print(f"ERROR: workbook not found: {p}")
    sys.exit(1)


def read_first_sheet(path):
    """Return (headers, data_rows) where data_rows is a list of (rownum, {col: text})."""
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet_el = next((el for el in wb.iter() if local(el.tag) == "sheet"), None)
        if sheet_el is None:
            print("ERROR: no sheets found in workbook.xml")
            sys.exit(1)
        rid = next(v for k, v in sheet_el.attrib.items() if local(k) == "id")

        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = None
        for el in rels.iter():
            if local(el.tag) == "Relationship" and el.get("Id") == rid:
                target = el.get("Target")
        if target is None:
            print("ERROR: relationship for first sheet not found")
            sys.exit(1)
        target = target.lstrip("/") if target.startswith("/") else "xl/" + target

        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = [si_text(si) for si in sst if local(si.tag) == "si"]

        sheet = ET.fromstring(z.read(target))

    rows = []
    seq = 0
    for row_el in sheet.iter():
        if local(row_el.tag) != "row":
            continue
        seq += 1
        rownum = int(row_el.get("r") or seq)
        cells = {}
        pos = 0
        for c in row_el:
            if local(c.tag) != "c":
                continue
            ref = c.get("r")
            idx = col_index(ref) if ref else pos
            cells[idx] = cell_value(c, shared)
            pos = idx + 1
        rows.append((rownum, cells))

    # first non-empty row is the header
    non_empty = [(n, c) for n, c in rows if any(str(v).strip() for v in c.values())]
    if not non_empty:
        print("ERROR: sheet is empty")
        sys.exit(1)
    _, header_cells = non_empty[0]
    width = max(header_cells) + 1
    headers = [header_cells.get(i, "").strip() for i in range(width)]
    data_rows = non_empty[1:]
    return headers, data_rows


# ---------- Field helpers ----------

def get(cells, hmap, name):
    idx = hmap.get(name)
    if idx is None:
        return ""
    return (cells.get(idx) or "").strip()


def snake(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def map_category(text):
    t = text.lower()
    for name, pat in CATEGORY_RULES:
        if re.search(pat, t):
            return name
    return "other"


def map_level(funding_level):
    fl = funding_level.lower()
    if re.search(r"central|national|union", fl):
        return "central", None
    if "state" in fl:
        return "state", None
    return "state", "level unclear in source"


def _iso(y, m, d):
    try:
        return dt.date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def to_iso(text, allow_serial=False):
    """Return YYYY-MM-DD if text contains a concrete date, else None."""
    if not text:
        return None
    s = str(text).strip()
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        return _iso(m.group(1), m.group(2), m.group(3))
    m = re.search(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})", s)
    if m:
        return _iso(m.group(3), m.group(2), m.group(1))
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s+(\d{4})", s)
    if m and m.group(2).lower()[:3] in MONTHS:
        return _iso(m.group(3), MONTHS[m.group(2).lower()[:3]], m.group(1))
    m = re.search(r"([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and m.group(1).lower()[:3] in MONTHS:
        return _iso(m.group(3), MONTHS[m.group(1).lower()[:3]], m.group(2))
    if allow_serial and re.fullmatch(r"\d{5}(?:\.\d+)?", s):
        d = dt.date(1899, 12, 30) + dt.timedelta(days=int(float(s)))
        return d.isoformat()
    return None


def split_sentences(text):
    return [s.strip() for s in re.split(r"[.;\n]+", text) if s.strip()]


def frag(s):
    return re.sub(r"\s+", " ", s).strip()[:200]


def to_num(text):
    try:
        x = float(text.replace(",", "").rstrip("."))
    except ValueError:
        return None
    return int(x) if x.is_integer() else x


# ---------- Rule extraction ----------

def build_rules(criteria):
    """Return (rules, unmapped_sentences). Only rules clearly stated in the text are added."""
    sentences = split_sentences(criteria)
    rules, mapped, counts = [], set(), {}

    def add(field, kind, op, value, i):
        base = f"{field}_{kind}"
        counts[base] = counts.get(base, 0) + 1
        rid = base if counts[base] == 1 else f"{base}_{counts[base]}"
        rules.append({"id": rid, "field": field, "op": op,
                      "value": value, "text": frag(sentences[i])})
        mapped.add(i)

    for i, sent in enumerate(sentences):
        s = sent.lower()

        # income (lakh form first, then bare rupee form)
        m = INCOME_LAKH.search(s)
        if m:
            amt = to_num(m.group(3))
            if amt is not None:
                add("annual_family_income", "max", "<=", int(round(amt * 100000)), i)
        else:
            m = INCOME_RUPEE.search(s)
            if m:
                amt = to_num(m.group(3))
                if amt is not None:
                    add("annual_family_income", "max", "<=", int(round(amt)), i)

        # age
        if re.search(r"\bage\b", s):
            m = AGE_RANGE.search(s)
            if m:
                add("age", "min", ">=", int(m.group(1)), i)
                add("age", "max", "<=", int(m.group(2)), i)
            else:
                m = AGE_MIN.search(s)
                if m:
                    add("age", "min", ">=", int(m.group(1)), i)
                m = AGE_MAX.search(s)
                if m:
                    add("age", "max", "<=", int(m.group(1)), i)

        # state residence
        if STATE_RE.search(s):
            add("state", "resident", "==", "Andhra Pradesh", i)

        # category (SC/ST/BC/OC/EWS/MINORITY)
        cats = [name for name, pat in CAT_PATTERNS if re.search(pat, s)]
        if cats:
            add("category", "eligible", "in", cats, i)

        # gender
        if GENDER_RE.search(s):
            add("gender", "female", "==", "female", i)

        # occupation
        if re.search(r"\bfarmers?\b", s):
            add("occupation", "farmer", "==", "farmer", i)
        if re.search(r"\bstudents?\b", s):
            add("occupation", "student", "==", "student", i)

        # land
        m = LAND_RE.search(s)
        if m:
            n = to_num(m.group(1))
            if n is not None:
                if re.search(r"up to|below|not exceed|maximum|less than", s):
                    add("land_acres", "max", "<=", n, i)
                elif re.search(r"at least|minimum", s):
                    add("land_acres", "min", ">=", n, i)

        # bank account required
        if "bank account" in s and re.search(
                r"require|must|should|need|mandatory|having|holding", s):
            add("has_bank_account", "required", "bool", True, i)

    unmapped = [sentences[i] for i in range(len(sentences)) if i not in mapped]
    return rules, unmapped


# ---------- YAML emission (hand-written, every string via json.dumps) ----------

def y(v):
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, list):
        return json.dumps(v, ensure_ascii=False)
    return json.dumps(str(v), ensure_ascii=False)


def emit_scheme(s):
    out = []
    for k in KEYS:
        v = s[k]
        if k == "rules":
            if not v:
                out.append("rules: []")
            else:
                out.append("rules:")
                for r in v:
                    out.append(f"  - id: {y(r['id'])}")
                    for kk in ("field", "op", "value", "text"):
                        out.append(f"    {kk}: {y(r[kk])}")
        elif k in ("documents", "steps"):
            if not v:
                out.append(f"{k}: []")
            else:
                out.append(f"{k}:")
                out.extend(f"  - {y(x)}" for x in v)
        else:
            out.append(f"{k}: {y(v)}")
    return "\n".join(out) + "\n"


# ---------- Curated overrides ----------

def load_overrides():
    if not OVERRIDES_PATH.exists():
        return {}
    import yaml  # PyYAML; only needed when the overrides file exists
    with OVERRIDES_PATH.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("schemes") or {}


def apply_overrides(schemes, overrides):
    known = {s["scheme_id"] for s in schemes}
    for sid in overrides:
        if sid not in known:
            print(f"WARNING: override for unknown scheme_id: {sid}")
    for s in schemes:
        ov = overrides.get(s["scheme_id"]) or {}
        rule_ids = {r["id"] for r in s["rules"]}
        contributed = False
        for r in ov.get("rules") or []:
            if r["id"] in rule_ids:
                continue
            s["rules"].append({"id": r["id"], "field": r["field"], "op": r["op"],
                               "value": r["value"], "text": r["text"]})
            rule_ids.add(r["id"])
            contributed = True

        unresolved = [str(u) for u in (ov.get("unresolved") or [])]
        s["unresolved_conditions"] = unresolved
        if not s["rules"]:
            s["rule_conversion_status"] = "not_structurable"
        elif unresolved:
            s["rule_conversion_status"] = "partial"
        else:
            s["rule_conversion_status"] = "converted"
        s["eligibility_source"] = "dataset eligibility_criteria" + (
            OVERRIDE_SOURCE if contributed else "")
        s["manual_verification_required"] = bool(
            unresolved or not s["rules"] or ov.get("manual_verification_required"))


# ---------- Main ----------

def build_schemes(headers, data_rows):
    hmap = {}
    for i, h in enumerate(headers):
        if h and h not in hmap:
            hmap[h] = i
    missing = [h for h in EXPECTED_HEADERS if h not in hmap]
    if missing:
        print(f"WARNING: expected headers not found: {missing}")
    status_key = STATUS_HEADER if STATUS_HEADER in hmap else next(
        (h for h in headers if h.lower().startswith("status")), None)

    schemes, used = [], set()
    for rownum, cells in data_rows:
        # every header cell as header -> text, so columns are read by name
        row = {h: (cells.get(i) or "").strip() for h, i in hmap.items()}
        name = get(cells, hmap, "scheme_name") or f"unnamed_row_{rownum}"
        base = snake(name) or f"scheme_row_{rownum}"
        sid, n = base, 2
        while sid in used:
            sid = f"{base}_{n}"
            n += 1
        used.add(sid)

        level, level_note = map_level(get(cells, hmap, "funding_level"))
        state = "All India" if level == "central" else "Andhra Pradesh"
        benefit = get(cells, hmap, "benefit")
        official = get(cells, hmap, "official_or_reference_url") or None
        status_text = get(cells, hmap, status_key) if status_key else ""
        criteria = get(cells, hmap, "eligibility_criteria")
        rules, unmapped = build_rules(criteria)

        dl_src = next((x for x in split_sentences(criteria) + split_sentences(benefit)
                       if DEADLINE_RE.search(x.lower())), None)
        deadline = frag(dl_src) if dl_src else None
        deadline_date = to_iso(dl_src) if dl_src else None

        docs_raw = get(cells, hmap, "required_documents_typical")
        documents = [d.strip() for d in re.split(r"[,;\n]+", docs_raw) if d.strip()]

        where_to_apply = row.get("where_how_to_apply", "") or None
        if where_to_apply:
            step2 = "Apply: " + where_to_apply
        elif official and re.match(r"https?://", official):
            step2 = f"Apply via the reference link: {official}"
        else:
            step2 = "Apply on the official portal"

        note_parts = list(unmapped)
        if level_note:
            note_parts.append(level_note)

        schemes.append({
            "scheme_id": sid,
            "name": name,
            "level": level,
            "state": state,
            "category": map_category(get(cells, hmap, "category")),
            "benefit": benefit,
            "official_source": official,
            "last_verified": to_iso(status_text, allow_serial=True),
            "verified_by": VERIFIED_BY,
            "criteria_text": criteria,
            "rules": rules,
            "documents": documents,
            "steps": ["Gather the documents listed above", step2,
                      "Note the application ID and keep the receipt"],
            "deadline": deadline,
            "deadline_date": deadline_date,
            "notes": " | ".join(note_parts),
            "where_to_apply": where_to_apply,
            "terms_and_conditions": row.get("terms_and_conditions", "") or None,
            "does_not_provide": row.get("what_it_does_not_provide", "") or None,
            "when_it_may_help": row.get("when_this_scheme_may_help", "") or None,
        })
    return schemes


def validate(schemes):
    errors = []
    ids = [s["scheme_id"] for s in schemes]
    for sid in {x for x in ids if ids.count(x) > 1}:
        errors.append(f"duplicate scheme_id: {sid}")
    for s in schemes:
        for k in KEYS:
            if k not in s:
                errors.append(f"{s.get('scheme_id')}: missing key {k}")
        for r in s["rules"]:
            if r["field"] not in ALLOWED_FIELDS:
                errors.append(f"{s['scheme_id']}: bad rule field {r['field']}")
            if r["op"] not in ALLOWED_OPS:
                errors.append(f"{s['scheme_id']}: bad rule op {r['op']}")
    return errors


def main():
    xlsx = find_xlsx()
    headers, data_rows = read_first_sheet(xlsx)
    print("Header row as read:", headers)

    schemes = build_schemes(headers, data_rows)
    if not schemes:
        print("ERROR: no data rows found")
        sys.exit(1)

    apply_overrides(schemes, load_overrides())
    errors = validate(schemes)

    SCHEMES_DIR.mkdir(parents=True, exist_ok=True)
    for s in schemes:
        (SCHEMES_DIR / f"{s['scheme_id']}.yaml").write_text(
            emit_scheme(s), encoding="utf-8")

    with LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scheme_id", "verified_by", "verified_date", "source_url", "notes"])
        for s in schemes:
            w.writerow([s["scheme_id"], VERIFIED_BY, s["last_verified"] or "",
                        s["official_source"] or "", ""])

    # re-read emitted YAML files to confirm every required top-level key is present
    for s in schemes:
        path = SCHEMES_DIR / f"{s['scheme_id']}.yaml"
        text = path.read_text(encoding="utf-8")
        for k in KEYS:
            if not re.search(rf"^{re.escape(k)}:", text, re.M):
                errors.append(f"{s['scheme_id']}: key {k} not found in written file")

    print(f"Scheme count: {len(schemes)}")
    for s in schemes:
        print(f"  {s['scheme_id']}: {len(s['rules'])} rule(s)")
    zero = sum(1 for s in schemes if not s["rules"])
    with_notes = sum(1 for s in schemes if s["notes"])
    with_when = sum(1 for s in schemes if s["when_it_may_help"])
    print(f"Zero-rule schemes: {zero}")
    print(f"Schemes with non-empty notes: {with_notes}")
    print(f"Schemes with non-empty when_it_may_help: {with_when}")
    converted = sum(1 for s in schemes if s["rule_conversion_status"] == "converted")
    partial = sum(1 for s in schemes if s["rule_conversion_status"] == "partial")
    not_struct = sum(1 for s in schemes if s["rule_conversion_status"] == "not_structurable")
    manual = sum(1 for s in schemes if s["manual_verification_required"])
    print(f"Rule conversion: converted={converted} partial={partial} "
          f"not_structurable={not_struct}")
    print(f"manual_verification_required true: {manual}")

    # verification_log.csv must have exactly one data row per scheme
    with LOG_PATH.open(encoding="utf-8") as f:
        log_rows = list(csv.reader(f))[1:]
    if len(log_rows) != len(schemes):
        errors.append(f"verification_log.csv has {len(log_rows)} rows, expected {len(schemes)}")

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("Validation OK")


if __name__ == "__main__":
    main()
