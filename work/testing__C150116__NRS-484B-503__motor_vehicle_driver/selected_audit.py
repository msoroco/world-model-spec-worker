"""Independent CPU audit of selected diagnostic bindings, without acceptance."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from passenger_zone import CASES

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + '__'
DIFFERENCES = {
    'conduct_without_passenger': 'conduct',
    'passenger_exception_activity': 'passenger_action',
    'activity_timing': 'release_delay_s',
    'effective_hours': 'hours',
}


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(relative, expected=None):
    need(isinstance(relative, str) and relative and not Path(relative).is_absolute()
         and '..' not in Path(relative).parts, 'unsafe proof path')
    path = HERE / relative
    need(path.is_file() and not path.is_symlink(), 'missing proof: ' + relative)
    if expected is not None:
        need(sha(path) == expected, 'stale proof: ' + relative)
    return path


def read(relative, expected=None):
    return json.loads(document(relative, expected).read_text(encoding='utf-8'))


def audit_case(entry):
    cid = entry.get('case_id')
    expected = next((case for case in CASES if cid == PREFIX + case.name), None)
    need(expected is not None and entry.get('kind') == 'delivery', 'wrong selected case')
    construction = read(entry['construction'], entry['construction_sha256'])
    need(construction.get('diagnostic_only') is True and construction.get('case_id') == cid,
         'selected source scope changed')
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    need(config.get('selected_case_id') == cid and config.get('rate_hz') == 20
         and config.get('duration_s') == 45 and config.get('cameras') ==
         ['overview', 'approach', 'reference_corner', 'driver_reference'],
         'selected capture profile changed')
    case = config['case']
    for key in ('conduct', 'passenger_action', 'release_delay_s', 'hours'):
        need(case.get(key) == getattr(expected, key), 'selected comparison variable changed: ' + key)
    scene = json.loads(next(item['content'] for item in construction['files']
                            if item['path'] == 'scene.json'))
    need(scene.get('case_id') == cid and scene.get('source_kind') == 'synthetic_diagnostic_fixture'
         and scene.get('accepted_original_source') is False, 'diagnostic scene provenance changed')
    receipt = read(entry['compatibility']['receipt'], entry['compatibility']['sha256'])
    need(receipt.get('passed') is True and receipt.get('case_id') == cid
         and receipt.get('candidate_id') == 'primary'
         and receipt.get('construction_sha256') == entry['construction_sha256']
         and receipt.get('scope') == 'diagnostic software compatibility only',
         'selected compatibility binding changed')
    need('negative_case_source' in receipt.get('checks', []), 'selected negative source test missing')
    document(entry['compatibility']['log'])
    document(entry['negative']['log'])
    need(entry['offline']['construction_sha256'] == entry['construction_sha256']
         and entry['offline']['exit_code'] == 0, 'selected offline binding changed')
    document(entry['offline']['log'], entry['offline']['log_sha256'])
    saved = entry['post_capture']
    need(saved.get('recorded_only') is True and saved.get('test_exit_code') == 0
         and saved.get('scope', '').startswith('synthetic recorded-only'),
         'selected saved-only proof changed')
    document(saved['test_log'], saved['test_log_sha256'])
    physical = read(entry['physical_preparation']['receipt'], entry['physical_preparation']['sha256'])
    need(physical.get('case_id') == cid and physical.get('construction_sha256') == entry['construction_sha256']
         and physical.get('diagnostic_fixture') is True, 'selected physical fixture binding changed')
    need([item['kind'] for item in physical['fixtures']] ==
         ['complete_motion', 'incomplete_motion', 'missing_evidence'], 'physical states missing')
    for item in physical['fixtures']:
        need(item['exit_code'] == 0, 'physical fixture test failed')
        document(item['log'], item['log_sha256'])
        document(item['result'], item['result_sha256'])
    lifecycle = physical['lifecycle']
    need(lifecycle['exit_code'] == 0 and lifecycle['events'] ==
         ['capture_finished', 'encoders_closed', 'restoration_verified', 'native_exit',
          'owner_released', 'saved_processing_started'], 'saved lifecycle order changed')
    document(lifecycle['log'], lifecycle['log_sha256'])
    return {'case_id': cid, 'construction_sha256': entry['construction_sha256'],
            'compatibility_receipt_sha256': entry['compatibility']['sha256'],
            'physical_receipt_sha256': entry['physical_preparation']['sha256'],
            'conduct': expected.conduct, 'passenger_action': expected.passenger_action,
            'release_delay_s': expected.release_delay_s, 'hours': expected.hours,
            'diagnostic_scene': scene,
            'source_kind': 'synthetic_diagnostic_fixture', 'physical_acceptance': False,
            'legal_status': 'unresolved'}


def audit_selected(manifest=None, plan=None):
    manifest = manifest or read('execution-manifest.json')
    plan = plan or read('case-plan.json')
    need(manifest.get('assignment_id') == HERE.name and
         manifest.get('status') == 'source_gated_draft', 'selected manifest scope changed')
    expected = {PREFIX + case.name for case in CASES}
    need({entry['case_id'] for entry in manifest['cases']} == expected
         and len(manifest['cases']) == len(expected), 'seven selected cases required')
    reports = {entry['case_id']: audit_case(entry) for entry in manifest['cases']}
    need({item['case_id'] for item in plan['cases']} == expected, 'plan and selection differ')
    comparisons = []
    need({item['comparison_id'] for item in plan['comparisons']} == set(DIFFERENCES),
         'four planned comparisons required')
    for item in plan['comparisons']:
        ids = item['case_ids']
        need(len(ids) >= 2 and len(ids) == len(set(ids)) and set(ids) <= expected,
             'comparison case identity changed')
        variable = DIFFERENCES[item['comparison_id']]
        anchor = reports[ids[0]]
        for cid in ids[1:]:
            other = reports[cid]
            need(anchor[variable] != other[variable], 'declared difference absent: ' + variable)
            fixed_keys = {'conduct', 'passenger_action', 'release_delay_s', 'hours'} - {variable}
            if variable == 'passenger_action' and 'none' in (anchor['passenger_action'], other['passenger_action']):
                fixed_keys.remove('release_delay_s')
            for fixed in fixed_keys:
                need(anchor[fixed] == other[fixed], 'fixed diagnostic variable changed: ' + fixed)
            left_scene = anchor['diagnostic_scene']
            right_scene = other['diagnostic_scene']
            for key in ('cell_id', 'layout', 'road', 'zone', 'vehicle_blueprint',
                        'vehicle_blueprint_source_sha256', 'passenger_blueprint',
                        'passenger_blueprint_source_sha256'):
                need(left_scene.get(key) == right_scene.get(key),
                     'fixed diagnostic scene changed: ' + key)
            left_reg, right_reg = dict(left_scene['regulations']), dict(right_scene['regulations'])
            left_clock, right_clock = dict(left_scene['clock']), dict(right_scene['clock'])
            if variable == 'hours':
                need(left_reg.pop('effective_at_civil_time') is True
                     and right_reg.pop('effective_at_civil_time') is False,
                     'diagnostic effective-hours difference absent')
                need(left_clock.pop('civil_time_iso') != right_clock.pop('civil_time_iso'),
                     'diagnostic civil-time difference absent')
            need(left_reg == right_reg and left_clock == right_clock,
                 'fixed diagnostic regulation or clock source changed')
        comparisons.append({'comparison_id': item['comparison_id'], 'case_ids': ids,
                            'declared_difference': variable, 'original_source_verified': False})
    return {'format': 'c150116-selected-diagnostic-audit-v1', 'assignment_id': HERE.name,
            'source_kind': 'synthetic_diagnostic_fixture', 'cases': list(reports.values()),
            'comparisons': comparisons, 'original_source_verified': False,
            'physical_acceptance': False, 'legal_status': 'unresolved'}


if __name__ == '__main__':
    print(json.dumps(audit_selected(), indent=2))
