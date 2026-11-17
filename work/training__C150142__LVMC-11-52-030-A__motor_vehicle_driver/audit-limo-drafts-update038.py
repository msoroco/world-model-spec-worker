"""Independently bind provisional limo constructions to offline/source proofs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARIES = {'below': (36120, 1799.95, 'below', 1),
              'at': (36121, 1800, 'at', 1),
              'above': (36122, 1800.05, 'above', 1),
              'no_loading': (36121, 1800, 'at', 0)}
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
ALLOWED = {'candidate_id', 'risk_trigger', 'requested_target_x_m',
           'camera_policy', 'tracks_sha256'}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    matrix = {row['case_id']: row for row in read(ROOT / 'exception-case-matrix.json')['cases']}
    manifest = read(ROOT / 'execution-manifest-diagnostic-limo_below-draft.json')
    entries = {row['case_id']: row for row in manifest['cases']}
    require(len(entries) == 4, 'Expected four limousine case boundaries')
    records = []
    for boundary, (frames, duration, relation, events) in BOUNDARIES.items():
        slug = boundary.replace('_', '-')
        case = 'limo_' + boundary
        case_id = ROOT.name + '__' + case
        plan = matrix[case_id]
        entry = entries[case_id]
        require(plan['service_class'] == 'limo' and
                plan['sign_classes'] == ['tour_bus', 'shuttle_bus', 'limo'] and
                plan['requested_stationary_duration_s'] == duration and
                plan['activity_request'] == (None if events == 0 else 'passenger_loading'),
                'Frozen limousine branch differs: ' + case)
        fallback_entries = {row['id']: row for row in entry['candidates']}
        require(set(fallback_entries) == set(CANDIDATES[1:]) and
                len({(row['trigger']['metric'], row['trigger']['failure_condition'])
                     for row in fallback_entries.values()}) == 3,
                'Distinct fallback risks missing: ' + case)
        configs = {}
        for candidate in CANDIDATES:
            package_path = ROOT / ('selected-primary' if candidate == 'primary'
                                   else 'selected-fallbacks') / case
            if candidate != 'primary':
                package_path /= candidate
            package_path /= 'construction.json'
            package = read(package_path)
            files = {row['path']: row['content'] for row in package['files']}
            config = json.loads(files['config.json'])
            manifest_row = entry if candidate == 'primary' else fallback_entries[candidate]
            require(manifest_row['construction_sha256'] == sha(package_path) and
                    package['case_id'] == config['case_id'] == config['selected_case_id'] == case_id and
                    config['candidate_id'] == candidate and
                    config['capture_frames'] == frames and
                    config['requested_stationary_duration_s'] == duration and
                    config['requested_boundary'] == relation and
                    config['native_blueprint'] == 'vehicle.lincoln.mkz_2020' and
                    config['service_class'] == 'limo' and
                    config['service_identity_source'] == 'authored_limo_service_plan_unverified' and
                    config['sign_classes'] == plan['sign_classes'] and
                    'limousine' in package['recording_description']['limitations'][-1].lower(),
                    'Provisional limousine construction differs: ' + case + '/' + candidate)
            offline_path = ROOT / f'update038-limo-{slug}-{candidate}-offline.log'
            source_path = ROOT / f'update038-limo-{slug}-{candidate}-source-proof.json'
            offline, source = read(offline_path), read(source_path)
            require(offline['case_id'] == case_id and offline['candidate_id'] == candidate and
                    offline['offline_passed'] is True and offline['simulation_started'] is False and
                    source['case_id'] == case_id and source['candidate'] == candidate and
                    source['source_kind'] == 'synthetic_native_sample' and
                    source['original_native_observed'] is False and
                    source['measured_duration_s'] == duration and source['boundary'] == relation and
                    source['activity_events'] == events and source['draft_text4_contract_passed'] is True and
                    source['missing_passenger_source_rejected'] is True and
                    source['media_decoded'] is False,
                    'Offline or source proof differs: ' + case + '/' + candidate)
            configs[candidate] = config
            records.append({'case_id': case_id, 'candidate_id': candidate,
                            'construction_sha256': sha(package_path),
                            'offline_sha256': sha(offline_path),
                            'source_proof_sha256': sha(source_path)})
        base = configs['primary']
        for candidate in CANDIDATES[1:]:
            other = configs[candidate]
            changed = {key for key in base.keys() | other.keys()
                       if base.get(key) != other.get(key)}
            require(changed <= ALLOWED and changed & {'requested_target_x_m', 'camera_policy'},
                    'Fallback changed fixed limousine scene: ' + case + '/' + candidate)
        require(configs['fallback1']['requested_target_x_m'] < base['requested_target_x_m'] <
                configs['fallback3']['requested_target_x_m'] and
                configs['fallback2']['camera_policy'] != base['camera_policy'],
                'Fallback mitigation differs from authored risk: ' + case)
    return {'format': 'c150142-limo-draft-audit-v1', 'passed': True,
            'records': records, 'original_native_observed': False,
            'limousine_service_verified': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
