"""Validation checks for the eligibility engine (engine/match.py).

Run from the project root:  python scratch/validate_engine.py
Prints one PASS/FAIL line per check. Exits 1 if any check FAILs.
"""

import json
import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.match import analyze, evaluate_rule, load_schemes, scheme_verdict  # noqa: E402

RESULTS = []


def check(name, passed, detail=""):
    RESULTS.append((name, bool(passed)))
    status = "PASS" if passed else "FAIL"
    print(f"{status}  {name}" + (f"  [{detail}]" if detail else ""))


def info(line):
    print(f"INFO  {line}")


def guarded(name, func):
    try:
        func()
    except Exception as exc:  # an uncaught exception counts as a FAIL for that section
        check(f"{name} (raised)", False, f"{type(exc).__name__}: {exc}")
        traceback.print_exc()


def rule(rule_id, field, op, value):
    return {"id": rule_id, "field": field, "op": op, "value": value,
            "text": f"{field} {op} {value}"}


def ev(field, op, value, profile):
    return evaluate_rule(rule("r_" + field, field, op, value), profile)["result"]


# ---------- a) operators ----------
CASES_A = [
    ("<=", "annual_family_income", 250000, 180000, "PASS"),
    ("<=", "annual_family_income", 250000, 300000, "FAIL"),
    (">=", "age", 60, 65, "PASS"),
    (">=", "age", 60, 50, "FAIL"),
    ("==", "state", "Andhra Pradesh", "Andhra Pradesh", "PASS"),
    ("==", "state", "Andhra Pradesh", "Karnataka", "FAIL"),
    ("in", "category", ["SC", "ST"], "SC", "PASS"),
    ("in", "category", ["SC", "ST"], "OC", "FAIL"),
    ("bool", "has_bank_account", True, True, "PASS"),
    ("bool", "has_bank_account", True, False, "FAIL"),
    ("!=", "occupation", "student", "farmer", "PASS"),
    ("!=", "occupation", "farmer", "farmer", "FAIL"),
    ("not_in", "category", ["SC", "ST"], "OC", "PASS"),
    ("not_in", "category", ["SC", "ST"], "SC", "FAIL"),
]


def section_a():
    for op, field, value, actual, expected in CASES_A:
        got = ev(field, op, value, {field: actual})
        check(f"a) {field} {op} {value!r} with actual {actual!r} -> {expected}",
              got == expected, f"got {got}")


# ---------- b) missing field ----------
def section_b():
    res = evaluate_rule(rule("r_income", "annual_family_income", "<=", 250000),
                        {"state": "Andhra Pradesh"})
    check("b) missing field -> UNVERIFIED", res["result"] == "UNVERIFIED",
          f"got {res['result']}")
    check("b) missing field explanation contains 'do not know'",
          "do not know" in res["explanation"], repr(res["explanation"]))


# ---------- c) groups ----------
def section_c():
    def income_ok():
        return rule("inc_ok", "annual_family_income", "<=", 250000)

    def state_ap():
        return rule("st_ap", "state", "==", "Andhra Pradesh")

    def state_ka():
        return rule("st_ka", "state", "==", "Karnataka")

    def age_60():
        return rule("age_60", "age", ">=", 60)

    cases = [
        ("c) all_of [PASS,PASS] -> PASS",
         {"id": "g", "all_of": [income_ok(), state_ap()]},
         {"annual_family_income": 180000, "state": "Andhra Pradesh"}, "PASS"),
        ("c) all_of with one FAIL -> FAIL",
         {"id": "g", "all_of": [income_ok(), state_ap()]},
         {"annual_family_income": 180000, "state": "Karnataka"}, "FAIL"),
        ("c) all_of with one UNVERIFIED and no FAIL -> UNVERIFIED",
         {"id": "g", "all_of": [income_ok(), state_ap()]},
         {"annual_family_income": 180000}, "UNVERIFIED"),
        ("c) any_of [FAIL,PASS] -> PASS",
         {"id": "g", "any_of": [income_ok(), state_ap()]},
         {"annual_family_income": 300000, "state": "Andhra Pradesh"}, "PASS"),
        ("c) any_of [FAIL,FAIL] -> FAIL",
         {"id": "g", "any_of": [income_ok(), state_ap()]},
         {"annual_family_income": 300000, "state": "Karnataka"}, "FAIL"),
        ("c) nested any_of inside all_of -> PASS",
         {"id": "g", "all_of": [income_ok(),
                                {"id": "n", "any_of": [state_ka(), age_60()]}]},
         {"annual_family_income": 180000, "state": "Andhra Pradesh", "age": 65}, "PASS"),
    ]
    for name, rl, profile, expected in cases:
        got = evaluate_rule(rl, profile)["result"]
        check(name, got == expected, f"got {got}")


# ---------- d) scheme_verdict ----------
def section_d():
    def inc():
        return rule("inc_ok", "annual_family_income", "<=", 250000)

    cases = [
        ("d) no rules -> needs_verification",
         {"scheme_id": "synthetic", "rules": []}, {"annual_family_income": 180000},
         "needs_verification"),
        ("d) all PASS + unresolved -> possibly_eligible (not likely)",
         {"scheme_id": "synthetic", "rules": [inc()],
          "unresolved_conditions": ["Valid ration card"]},
         {"annual_family_income": 180000}, "possibly_eligible"),
        ("d) all PASS, no unresolved -> likely_eligible",
         {"scheme_id": "synthetic", "rules": [inc()]},
         {"annual_family_income": 180000}, "likely_eligible"),
        ("d) a FAIL -> not_eligible",
         {"scheme_id": "synthetic", "rules": [inc()]},
         {"annual_family_income": 300000}, "not_eligible"),
        ("d) one UNVERIFIED -> possibly_eligible",
         {"scheme_id": "synthetic", "rules": [inc()]},
         {}, "possibly_eligible"),
    ]
    for name, scheme, profile, expected in cases:
        verdict, _ = scheme_verdict(scheme, profile)
        check(name, verdict == expected, f"got {verdict}")


# ---------- e) real data, converted schemes ----------
def section_e():
    schemes = load_schemes()
    converted = [s for s in schemes if s.get("rule_conversion_status") == "converted"]
    info(f"e) converted schemes: {len(converted)}")
    for s in converted:
        info(f"e)   {s.get('scheme_id')}  rules={len(s.get('rules') or [])}  "
             f"manual_verification_required={bool(s.get('manual_verification_required'))}  "
             f"unresolved={len(s.get('unresolved_conditions') or [])}")
    flagged = [s.get("scheme_id") for s in converted
               if bool(s.get("manual_verification_required"))
               and s.get("unresolved_conditions")]
    info(f"e) converted with manual_verification_required=True AND unresolved_conditions: "
         f"{len(flagged)} -> {flagged}")
    bad_manual = [s.get("scheme_id") for s in converted
                  if s.get("manual_verification_required")
                  and not s.get("unresolved_conditions")]
    check("e) converted schemes: manual_verification_required False OR has unresolved_conditions",
          not bad_manual, f"offending: {bad_manual}")
    no_rules = [s.get("scheme_id") for s in converted if not s.get("rules")]
    check("e) each converted scheme has at least one rule", not no_rules,
          f"without rules: {no_rules}")


# ---------- f) real data, status counts ----------
def section_f():
    schemes = load_schemes()
    by_status = Counter(str(s.get("rule_conversion_status")) for s in schemes)
    by_manual = Counter(str(bool(s.get("manual_verification_required"))) for s in schemes)
    for key, count in sorted(by_status.items()):
        info(f"f) rule_conversion_status {key}: {count}")
    for key, count in sorted(by_manual.items()):
        info(f"f) manual_verification_required {key}: {count}")
    total = sum(by_status.values())
    expected = {"converted": 11, "partial": 4, "not_structurable": 16}
    info(f"f) expected converted 11 / partial 4 / not_structurable 16; "
         f"actual matches expectation: "
         f"{all(by_status.get(k, 0) == v for k, v in expected.items())}")
    check("f) status counts sum to 31", total == 31,
          f"sum {total}, loaded {len(schemes)} schemes")


# ---------- g) missing / incomplete profiles ----------
def _bad_g_reasons(out):
    bad = []
    for res in out["results"]:
        for reason in res["reasons"]:
            if "do not know" in reason["explanation"] and reason["result"] != "UNVERIFIED":
                bad.append(f"{res['scheme_id']}:{reason['rule_id']} result={reason['result']}")
        if res["rule_conversion_status"] in ("partial", "not_structurable") \
                and res["verdict"] == "likely_eligible":
            bad.append(f"{res['scheme_id']} likely_eligible with status "
                       f"{res['rule_conversion_status']}")
    return bad


def section_g():
    for text in ["", "I am 17 in Andhra Pradesh"]:
        try:
            out = analyze(text)
        except Exception as exc:
            check(f"g) analyze({text!r}) returns without exception", False,
                  f"{type(exc).__name__}: {exc}")
            continue
        check(f"g) analyze({text!r}) returns without exception", True)
        check(f"g) analyze({text!r}) results is a list", isinstance(out.get("results"), list))
        bad = _bad_g_reasons(out)
        check(f"g) analyze({text!r}): 'do not know' reasons are UNVERIFIED and no "
              f"partial/not_structurable is likely_eligible", not bad, f"offending: {bad}")


# ---------- h) false-positive checks ----------
def _leaf_rules(rules):
    for rl in rules or []:
        children = (rl.get("all_of") or []) + (rl.get("any_of") or [])
        if children:
            yield from _leaf_rules(children)
        else:
            yield rl


def _has_ap_state_rule(scheme):
    return any(rl.get("field") == "state" and rl.get("value") == "Andhra Pradesh"
               for rl in _leaf_rules(scheme.get("rules")))


def section_h():
    # (i) Karnataka daily-wage worker: no AP-only scheme may be likely_eligible.
    text_i = "I am 30, I live in Karnataka, I am a daily wage worker"
    out = analyze(text_i)
    profile = out["profile"]
    ap_schemes = [s for s in load_schemes() if _has_ap_state_rule(s)]
    ap_ids = {s.get("scheme_id") for s in ap_schemes}
    info(f"h(i) profile extracted: {profile}")
    info(f"h(i) schemes carrying an Andhra Pradesh state rule: {len(ap_schemes)}")
    bad_results = [r["scheme_id"] for r in out["results"]
                   if r["verdict"] == "likely_eligible" and r["scheme_id"] in ap_ids]
    bad_direct = [s.get("scheme_id") for s in ap_schemes
                  if scheme_verdict(s, profile)[0] == "likely_eligible"]
    check("h(i) Karnataka daily-wage: no AP-state scheme is likely_eligible",
          not bad_results and not bad_direct,
          f"in results: {bad_results}; direct check: {bad_direct}")

    # (ii) Age 65 in AP: ntr_bharosa_old_age_pension must not be likely_eligible.
    target = "ntr_bharosa_old_age_pension"
    out2 = analyze("I am 65 years old in Andhra Pradesh")
    by_id = {s.get("scheme_id"): s for s in load_schemes()}
    if target not in by_id:
        check(f"h(ii) {target} exists in data", False, "scheme_id not found")
    else:
        in_results = [r for r in out2["results"] if r["scheme_id"] == target]
        if in_results:
            verdict = in_results[0]["verdict"]
            where = "from results"
        else:
            verdict = scheme_verdict(by_id[target], out2["profile"])[0]
            where = "not in results (filtered out); verdict computed directly"
        info(f"h(ii) unresolved_conditions of {target}: "
             f"{len(by_id[target].get('unresolved_conditions') or [])}")
        check(f"h(ii) {target} is NOT likely_eligible", verdict != "likely_eligible",
              f"verdict={verdict}, {where}")

    # (iii) Six sample profiles: every likely_eligible must be converted.
    lik_all = []
    profile_files = sorted((ROOT / "tests" / "sample_profiles").glob("*.json"))
    info(f"h(iii) sample profiles run: {len(profile_files)}")
    for path in profile_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        res = analyze(data["text"])
        liks = [r for r in res["results"] if r["verdict"] == "likely_eligible"]
        listing = [(r["scheme_id"], r["rule_conversion_status"]) for r in liks]
        info(f"h(iii) {path.name}: likely_eligible -> {listing if listing else 'none'}")
        lik_all.extend((path.name, r["scheme_id"], r["rule_conversion_status"]) for r in liks)
    non_converted = [item for item in lik_all if item[2] != "converted"]
    check("h(iii) every likely_eligible scheme across sample profiles is converted",
          not non_converted,
          f"{len(lik_all)} likely_eligible results; non-converted: {non_converted}")


# ---------- i) output keys ----------
def section_i():
    out = analyze("I am a farmer in Andhra Pradesh with 2 acres of land, "
                  "my annual income is 90000 rupees")
    top_keys = ["results", "not_matching", "questions", "missing_fields",
                "selection_note", "disclaimer", "profile", "warnings"]
    missing_top = [k for k in top_keys if k not in out]
    check("i) analyze output has all top-level keys", not missing_top,
          f"missing: {missing_top}")
    info(f"i) results returned: {len(out.get('results', []))}")
    need = ["verdict", "reasons", "unresolved_conditions",
            "rule_conversion_status", "manual_verification_required"]
    bad = []
    for res in out.get("results", []):
        for key in need:
            if key not in res:
                bad.append(f"{res.get('scheme_id')}:{key}")
    check("i) each result has verdict, reasons, unresolved_conditions, "
          "rule_conversion_status, manual_verification_required",
          out.get("results") and not bad, f"missing: {bad}")


def main():
    guarded("a) operators", section_a)
    guarded("b) missing field", section_b)
    guarded("c) groups", section_c)
    guarded("d) scheme_verdict", section_d)
    guarded("e) real data converted", section_e)
    guarded("f) real data counts", section_f)
    guarded("g) incomplete profiles", section_g)
    guarded("h) false-positive", section_h)
    guarded("i) output keys", section_i)
    failed = [name for name, passed in RESULTS if not passed]
    print()
    print(f"SUMMARY: {len(RESULTS) - len(failed)} PASS, {len(failed)} FAIL "
          f"out of {len(RESULTS)} checks")
    for name in failed:
        print(f"  FAILED: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
