"""Audit the unsigned emergency worker/no-worker controlled comparison."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT.name
BUSINESS = BASE + '__emergency_vehicle_unsigned_business'
NO_WORKER = BASE + '__emergency_vehicle_unsigned_no_business'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(case, candidate):
    suffix = case.removeprefix(BASE + '__')
    path = ROOT / ('selected-primary' if candidate == 'primary' else
                   'selected-fallbacks') / suffix
    if candidate != 'primary':
        path /= candidate
    path /= 'construction.json'
    document = json.loads(path.read_text())
    files = {row['path']: row['content'] for row in document['files']}
    return document, files, json.loads(files['config.json'])


def check(config_overrides=None, summary_overrides=None):
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    pair = next(row for row in plan['comparisons']
                if row['comparison_id'] == BASE + '__emergency_vehicle_unsigned_business_pair')
    if pair['case_ids'] != [BUSINESS, NO_WORKER] or \
            pair['deliberate_differences'] != ['business_activity_event']:
        raise ValueError('Exact business comparison scope differs')
    summaries = {
        BUSINESS: json.loads((ROOT / 'update040-emergency-business-saved-matrix.json').read_text()),
        NO_WORKER: json.loads((ROOT / 'update040-emergency-no-business-saved-matrix.json').read_text())}
    if summary_overrides:
        summaries.update(summary_overrides)
    for candidate in CANDIDATES:
        _, business_files, business = package(BUSINESS, candidate)
        _, absent_files, absent = package(NO_WORKER, candidate)
        if config_overrides:
            business = config_overrides.get((BUSINESS, candidate), business)
            absent = config_overrides.get((NO_WORKER, candidate), absent)
        differing = {key for key in set(business) | set(absent)
                     if business.get(key) != absent.get(key)}
        if differing != {'case_id', 'selected_case_id', 'supported_case_ids',
                         'activity_request'}:
            raise ValueError('Comparison changed fixed config: ' + candidate)
        if business['activity_request'] != 'business_activity' or \
                absent['activity_request'] is not None:
            raise ValueError('Business activity contrast differs')
        for name in ('red-curb-road.xodr', 'requested-tracks.jsonl',
                     'assignment-source.json', 'case-plan.json',
                     'parking_controller.py', 'measure_exceptions.py'):
            if business_files[name] != absent_files[name]:
                raise ValueError('Comparison changed fixed source: ' + name)
        saved_rows = {}
        for case, label in ((BUSINESS, 'emergency-business'),
                            (NO_WORKER, 'emergency-no-business')):
            rows = {row['candidate']: row for row in summaries[case]['candidates']}
            if set(rows) != set(CANDIDATES) or rows[candidate]['frames'] != 361 or \
                    rows[candidate]['stationary_duration_s'] != 12 or \
                    rows[candidate]['four_source_decodes'] is not True or \
                    rows[candidate]['full_final_decode'] is not True:
                raise ValueError('Terminal comparison candidate missing: ' + case)
            saved_rows[case] = rows[candidate]
            attempt = REPO / '.runtime-work' / f'c150142-{label}-{candidate}-native-v1'
            version = REPO / '.runtime-work' / (
                f'c150142-{label}-{candidate}-result-' +
                ('v2' if case == BUSINESS and candidate == 'primary' else 'v1')) / 'v0001'
            result = json.loads((version / 'analysis/result.json').read_text())
            observation = result['measured_values']['signed_curb_observation']
            expected_events = ['business_activity'] if case == BUSINESS else []
            if result['case_id'] != case or \
                    [event['name'] for event in observation['recorded_activity_events']] != expected_events or \
                    observation['red_curb_stationary_duration_s'] != 12 or \
                    observation['necessary_business_established'] is not None:
                raise ValueError('Saved activity comparison differs: ' + case)
            for name in ('native-raw-actors.jsonl', 'native-map-readback.json',
                         'video_frames.jsonl', 'trace.jsonl', 'road.xodr',
                         'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                         'driver_reference.mkv'):
                other_label = 'emergency-no-business' if label == 'emergency-business' else 'emergency-business'
                other = REPO / '.runtime-work' / f'c150142-{other_label}-{candidate}-native-v1' / name
                if sha(attempt / name) != sha(other):
                    raise ValueError('Comparison raw fixed source differs: ' + candidate + '/' + name)
        if saved_rows[BUSINESS]['business_activity_source_derived'] is not True or \
                saved_rows[NO_WORKER]['empty_worker_inventory_source_derived'] is not True or \
                saved_rows[NO_WORKER]['actual_business_absence_established'] is not False:
            raise ValueError('Source activity comparison proof missing')
    return {'comparison_id': pair['comparison_id'],
            'candidates_compared': list(CANDIDATES),
            'fixed_config_and_raw_sources_checked': True,
            'worker_activity_isolated': True,
            'actual_business_absence_established': False,
            'necessary_business_established': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
