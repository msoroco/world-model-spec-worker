"""Independently compare saved C125751 measurements and fixed sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import audit as audit_delivery
from entry_timing import ASSIGNMENT


def compare_verified(comparison_id, results, survey_hashes):
    plan = json.loads((Path(__file__).resolve().parent/'case-plan.json').read_text())
    matches = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('unknown exact crossing comparison')
    case_ids = matches[0]['case_ids']
    if set(results) != set(case_ids) or set(survey_hashes) != set(case_ids):
        raise ValueError('comparison exact cases differ')
    if len(set(survey_hashes.values())) != 1:
        raise ValueError('comparison original crossing survey changed')
    rows = {row['case_id']:row for row in plan['cases']}
    if any(case not in rows for case in case_ids):
        raise ValueError('comparison case plan missing')
    if any(results[case].get('case_id') != case for case in case_ids):
        raise ValueError('comparison saved case differs')
    observed = [results[case]['measured_values'] for case in case_ids]
    if any(value.get('statutory_applicability') != 'unresolved_official_device_exclusion_and_subsection_4'
           for value in observed):
        raise ValueError('comparison legal boundary changed')
    if comparison_id == 'precedence_response':
        if len({rows[case]['requested_entry_difference_s'] for case in case_ids}) != 1:
            raise ValueError('response comparison timing target changed')
        if len({value['observed_ego_response'] for value in observed}) != 2:
            raise ValueError('response comparison lacks measured response contrast')
        difference = 'measured ego entry relative to other full-body exit'
    elif comparison_id == 'approximately_same_time_brackets':
        if len({rows[case]['requested_ego_response'] for case in case_ids}) != 1:
            raise ValueError('timing comparison response target changed')
        if len({value['observed_ego_response'] for value in observed}) != 1:
            raise ValueError('timing comparison measured response changed')
        values = [value['ego_minus_other_upper_entry_s'] for value in observed]
        if not values[0] < values[1] < values[2]:
            raise ValueError('timing comparison lacks measured bracket ordering')
        difference = 'measured ego-minus-other upper entry time ordered across three probes'
    else:
        raise ValueError('unsupported exact crossing comparison')
    return {'assignment_id':ASSIGNMENT, 'comparison_id':comparison_id,
            'case_ids':case_ids, 'fixed_original_survey_sha256':survey_hashes[case_ids[0]],
            'measured_difference':difference, 'legal_judgment':'unresolved',
            'physical_acceptance_claimed':False}


def audit_comparison(comparison_id, attempts, surveys):
    if set(attempts) != set(surveys):
        raise ValueError('comparison attempt/survey cases differ')
    results, hashes = {}, {}
    for case,attempt in attempts.items():
        if not case.startswith(ASSIGNMENT+'__'):
            raise ValueError('foreign crossing case')
        audit_delivery(attempt,surveys[case])
        results[case] = json.loads((Path(attempt)/'result.json').read_text())
        hashes[case] = hashlib.sha256(Path(surveys[case]).read_bytes()).hexdigest()
    return compare_verified(comparison_id,results,hashes)
