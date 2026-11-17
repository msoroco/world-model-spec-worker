"""Independently audit text-6 emergency no-worker draft candidates."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASE = ROOT.name + '__emergency_vehicle_signed_no_business'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(manifest=None, packages=None, saved=None):
    manifest = manifest or json.loads((ROOT / 'execution-manifest-diagnostic-emergency-signed-no-business-draft.json').read_text())
    saved = saved or json.loads((ROOT / 'update041-emergency-signed-no-business-saved-matrix.json').read_text())
    entries = manifest.get('cases')
    if len(entries) != 1 or entries[0]['case_id'] != CASE or \
            [row['id'] for row in entries[0]['candidates']] != list(CANDIDATES[1:]):
        raise ValueError('Emergency case or candidate identity differs')
    entry = entries[0]
    if entry['kind'] != 'delivery' or entry['candidate_risk']['status'] != 'physical':
        raise ValueError('Physical candidate risk missing')
    packages = packages or {}
    configs = {}
    source_files = {}
    for candidate in CANDIDATES:
        row = entry if candidate == 'primary' else next(
            value for value in entry['candidates'] if value['id'] == candidate)
        path = ROOT / row['construction']
        if row['construction_sha256'] != digest(path):
            raise ValueError('Candidate construction hash differs: ' + candidate)
        package = packages.get(candidate) or json.loads(path.read_text())
        files = {value['path']: value['content'] for value in package['files']}
        config = json.loads(files['config.json'])
        if package['case_id'] != CASE or config['case_id'] != CASE or \
                config['candidate_id'] != candidate or \
                config['sign_classes'] != ['armored_or_emergency'] or \
                config['service_class'] != 'emergency_vehicle' or \
                config['native_blueprint'] != 'vehicle.carlamotors.firetruck' or \
                config['activity_request'] is not None or \
                config['requested_stationary_duration_s'] != 12 or \
                config['capture_frames'] != 361 or \
                len(json.loads(files['case-plan.json'])['cases']) < 1:
            raise ValueError('Emergency fixed conditions differ: ' + candidate)
        if config['road_sha256'] != hashlib.sha256(files['red-curb-road.xodr'].encode()).hexdigest() or \
                config['tracks_sha256'] != hashlib.sha256(files['requested-tracks.jsonl'].encode()).hexdigest():
            raise ValueError('Road or controller trace hash differs: ' + candidate)
        configs[candidate] = config
        source_files[candidate] = files
        offline = ROOT / f'update041-emergency-signed-no-business-{candidate}-offline.log'
        proof = ROOT / f'update041-emergency-signed-no-business-{candidate}-source-proof.json'
        if json.loads(offline.read_text()).get('offline_passed') is not True or \
                json.loads(proof.read_text()) != {
                    'actual_business_absence_established': False,
                    'candidate_id': candidate, 'case_id': CASE,
                    'measured_stationary_duration_s': 12,
                    'missing_sign_rejected': True, 'media_decoded': False, 'missing_inventory_rejected': True,
                    'necessary_business_established': False,
                    'no_worker_inventory_derived': True,
                    'original_native_observed': False,
                    'source_kind': 'synthetic_native_sample',
                    'unexpected_worker_rejected': True}:
            raise ValueError('Offline or source negative proof missing: ' + candidate)
    baseline = configs['primary']
    for candidate in CANDIDATES[1:]:
        config = configs[candidate]
        allowed = {'candidate_id', 'risk_trigger', 'tracks_sha256',
                   'requested_target_x_m', 'camera_policy'}
        changed = {key for key in set(baseline) | set(config)
                   if baseline.get(key) != config.get(key)}
        if not changed <= allowed:
            raise ValueError('Fallback changed fixed configuration: ' + candidate)
        fixed_files = set(source_files['primary']) - {
            'config.json', 'requested-tracks.jsonl', 'tests/test_selected.py'}
        if any(source_files['primary'][name] != source_files[candidate][name]
               for name in fixed_files):
            raise ValueError('Fallback changed fixed construction file: ' + candidate)
        tracks = lambda name: [json.loads(line) for line in
                               source_files[name]['requested-tracks.jsonl'].splitlines()]
        if len(tracks(candidate)) != 120:
            raise ValueError('Fallback approach trace incomplete')
        if candidate == 'fallback2' and tracks(candidate) != tracks('primary'):
            raise ValueError('Camera fallback changed controller trace')
    if [(configs[c]['requested_target_x_m'], configs[c]['camera_policy']) for c in CANDIDATES] != [
            (40, 'standard'), (38, 'standard'), (40, 'elevated_overview'),
            (42, 'standard')]:
        raise ValueError('Fallback risk mechanisms differ')
    triggers = [row['trigger']['failure_condition'] for row in entry['candidates']]
    if len(set(triggers)) != 3 or any(not value for value in triggers):
        raise ValueError('Distinct physical-risk triggers missing')
    receipts = {row['candidate']: row for row in saved['candidates']}
    if set(receipts) != set(CANDIDATES) or any(
            receipts[c]['construction_sha256'] != entry['construction_sha256']
            if c == 'primary' else receipts[c]['construction_sha256'] != next(
                row['construction_sha256'] for row in entry['candidates'] if row['id'] == c)
            for c in CANDIDATES):
        raise ValueError('Saved candidate binding differs')
    if any(receipts[c]['frames'] != 361 or
           receipts[c]['four_source_decodes'] is not True or
           receipts[c]['full_final_decode'] is not True or
           receipts[c]['necessary_business_established'] is not False
           for c in CANDIDATES):
        raise ValueError('Terminal saved proof missing')
    return {'case_id': CASE, 'candidates': list(CANDIDATES),
            'fixed_conditions_checked': True, 'distinct_physical_triggers': 3,
            'offline_source_negative_and_terminal_saved_checked': True,
            'physical_acceptance_claimed': False,
            'necessary_business_established': False}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
