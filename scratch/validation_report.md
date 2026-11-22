# Engine validation report

## Step 1: pytest (python -m pytest tests/test_matching.py -q)
Exit code 0. Summary: 19 passed, 1 warning in 1.32s.

## Step 3: python scratch/validate_engine.py
Exit code: 0

```text
PASS  a) annual_family_income <= 250000 with actual 180000 -> PASS  [got PASS]
PASS  a) annual_family_income <= 250000 with actual 300000 -> FAIL  [got FAIL]
PASS  a) age >= 60 with actual 65 -> PASS  [got PASS]
PASS  a) age >= 60 with actual 50 -> FAIL  [got FAIL]
PASS  a) state == 'Andhra Pradesh' with actual 'Andhra Pradesh' -> PASS  [got PASS]
PASS  a) state == 'Andhra Pradesh' with actual 'Karnataka' -> FAIL  [got FAIL]
PASS  a) category in ['SC', 'ST'] with actual 'SC' -> PASS  [got PASS]
PASS  a) category in ['SC', 'ST'] with actual 'OC' -> FAIL  [got FAIL]
PASS  a) has_bank_account bool True with actual True -> PASS  [got PASS]
PASS  a) has_bank_account bool True with actual False -> FAIL  [got FAIL]
PASS  a) occupation != 'student' with actual 'farmer' -> PASS  [got PASS]
PASS  a) occupation != 'farmer' with actual 'farmer' -> FAIL  [got FAIL]
PASS  a) category not_in ['SC', 'ST'] with actual 'OC' -> PASS  [got PASS]
PASS  a) category not_in ['SC', 'ST'] with actual 'SC' -> FAIL  [got FAIL]
PASS  b) missing field -> UNVERIFIED  [got UNVERIFIED]
PASS  b) missing field explanation contains 'do not know'  ['We do not know your annual_family_income yet.']
PASS  c) all_of [PASS,PASS] -> PASS  [got PASS]
PASS  c) all_of with one FAIL -> FAIL  [got FAIL]
PASS  c) all_of with one UNVERIFIED and no FAIL -> UNVERIFIED  [got UNVERIFIED]
PASS  c) any_of [FAIL,PASS] -> PASS  [got PASS]
PASS  c) any_of [FAIL,FAIL] -> FAIL  [got FAIL]
PASS  c) nested any_of inside all_of -> PASS  [got PASS]
PASS  d) no rules -> needs_verification  [got needs_verification]
PASS  d) all PASS + unresolved -> possibly_eligible (not likely)  [got possibly_eligible]
PASS  d) all PASS, no unresolved -> likely_eligible  [got likely_eligible]
PASS  d) a FAIL -> not_eligible  [got not_eligible]
PASS  d) one UNVERIFIED -> possibly_eligible  [got possibly_eligible]
INFO  e) converted schemes: 11
INFO  e)   annadata_sukhibhava_pm_kisan  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   bc_welfare_post_matric_scholarship_fee_reimbursement  rules=2  manual_verification_required=False  unresolved=0
INFO  e)   jagjeevan_jyothi_sc_household_electricity_support  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   kapu_nestham  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   pm_kisan  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   pm_ujjwala_yojana_pmuy  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   post_matric_scholarship_rtf_mtf  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   pre_matric_scholarship  rules=2  manual_verification_required=False  unresolved=0
INFO  e)   residential_schools_and_hostels  rules=1  manual_verification_required=False  unresolved=0
INFO  e)   sc_welfare_scholarships_and_hostels  rules=2  manual_verification_required=False  unresolved=0
INFO  e)   stree_shakti_free_bus_travel  rules=1  manual_verification_required=False  unresolved=0
INFO  e) converted with manual_verification_required=True AND unresolved_conditions: 0 -> []
PASS  e) converted schemes: manual_verification_required False OR has unresolved_conditions  [offending: []]
PASS  e) each converted scheme has at least one rule  [without rules: []]
INFO  f) rule_conversion_status converted: 11
INFO  f) rule_conversion_status not_structurable: 16
INFO  f) rule_conversion_status partial: 4
INFO  f) manual_verification_required False: 11
INFO  f) manual_verification_required True: 20
INFO  f) expected converted 11 / partial 4 / not_structurable 16; actual matches expectation: True
PASS  f) status counts sum to 31  [sum 31, loaded 31 schemes]
PASS  g) analyze('') returns without exception
PASS  g) analyze('') results is a list
PASS  g) analyze(''): 'do not know' reasons are UNVERIFIED and no partial/not_structurable is likely_eligible  [offending: []]
PASS  g) analyze('I am 17 in Andhra Pradesh') returns without exception
PASS  g) analyze('I am 17 in Andhra Pradesh') results is a list
PASS  g) analyze('I am 17 in Andhra Pradesh'): 'do not know' reasons are UNVERIFIED and no partial/not_structurable is likely_eligible  [offending: []]
INFO  h(i) profile extracted: {'age': 30, 'occupation': 'daily_wage'}
INFO  h(i) schemes carrying an Andhra Pradesh state rule: 4
PASS  h(i) Karnataka daily-wage: no AP-state scheme is likely_eligible  [in results: []; direct check: []]
INFO  h(ii) unresolved_conditions of ntr_bharosa_old_age_pension: 4
PASS  h(ii) ntr_bharosa_old_age_pension is NOT likely_eligible  [verdict=possibly_eligible, from results]
INFO  h(iii) sample profiles run: 6
INFO  h(iii) daily_wage_ap.json: likely_eligible -> [('kapu_nestham', 'converted'), ('stree_shakti_free_bus_travel', 'converted')]
INFO  h(iii) farmer_ap.json: likely_eligible -> [('annadata_sukhibhava_pm_kisan', 'converted'), ('pm_kisan', 'converted')]
INFO  h(iii) out_of_state.json: likely_eligible -> none
INFO  h(iii) senior_ap.json: likely_eligible -> none
INFO  h(iii) student_bsc_ap.json: likely_eligible -> none
INFO  h(iii) woman_business_ap.json: likely_eligible -> [('kapu_nestham', 'converted'), ('stree_shakti_free_bus_travel', 'converted')]
PASS  h(iii) every likely_eligible scheme across sample profiles is converted  [6 likely_eligible results; non-converted: []]
PASS  i) analyze output has all top-level keys  [missing: []]
INFO  i) results returned: 10
PASS  i) each result has verdict, reasons, unresolved_conditions, rule_conversion_status, manual_verification_required  [missing: []]

SUMMARY: 41 PASS, 0 FAIL out of 41 checks

```
