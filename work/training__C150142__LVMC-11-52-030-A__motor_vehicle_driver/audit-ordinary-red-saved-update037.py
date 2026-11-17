"""Independently compare the four current-runtime ordinary signed-curb paths."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
EXPECTED_SECONDS = {'primary': 5.95, 'fallback1': 2.95,
                    'fallback2': 5.95, 'fallback3': 7.45}
ALLOWED_CHANGES = {'candidate_id', 'risk_trigger', 'tracks_sha256',
                   'requested_approach_frames', 'camera_policy'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stage(candidate):
    name = ('c150142-ordinary-red-saved-result-update037'
            if candidate == 'primary' else
            f'c150142-ordinary-red-{candidate}-saved-result-update037')
    return REPO / '.runtime-work' / name / 'v0001'


def audit():
    manifest = read(ROOT / 'execution-manifest-diagnostic-ordinary_red_signed.json')
    entry = manifest['cases'][0]
    case = ROOT.name + '__ordinary_red_signed'
    require(entry['case_id'] == case, 'Signed case identity changed')
    alternatives = {row['id']: row for row in entry['candidates']}
    require(set(alternatives) == set(CANDIDATES[1:]), 'Fallback set changed')
    triggers = {(row['trigger']['metric'], row['trigger']['failure_condition'])
                for row in alternatives.values()}
    require(len(triggers) == 3, 'Physical-risk triggers overlap')
    configs = {}
    records = []
    for candidate in CANDIDATES:
        version = stage(candidate)
        summary_name = ('update037-ordinary-red-pinned-saved.json'
                        if candidate == 'primary' else
                        f'update037-ordinary-red-{candidate}-pinned-saved.json')
        compatibility_name = ('update037-ordinary-red-compat.json'
                              if candidate == 'primary' else
                              f'update037-ordinary-red-{candidate}-candidate-compat.json')
        negative_name = ('update037-ordinary-red-saved-negative.json'
                         if candidate == 'primary' else
                         f'update037-ordinary-red-{candidate}-saved-negative.json')
        summary = read(ROOT / summary_name)
        compatibility = read(ROOT / compatibility_name)
        negative = read(ROOT / negative_name)
        processing = read(version / 'processing.json')
        selection = read(version / 'analysis/candidate-selection.json')
        config = read(version / 'analysis/config.json')
        report = read(version / 'analysis/analysis-report.json')
        expected_hash = (entry['construction_sha256'] if candidate == 'primary'
                         else alternatives[candidate]['construction_sha256'])
        require(processing['passed'] is True and
                processing['candidate_id'] == selection['candidate_id'] == candidate and
                processing['analysis_revision']['construction_sha256'] ==
                selection['construction_sha256'] == expected_hash and
                processing['originals_preserved'] is True and
                processing['missing_evidence'] is False,
                'Pinned saved candidate identity differs: ' + candidate)
        require(summary['case_id'] == case and
                summary['candidate_id'] == candidate and
                summary['processing_sha256'] == sha(version / 'processing.json') and
                summary['construction_sha256'] == expected_hash and
                summary['timestamp_join_frames'] == summary['final_decode_frames'] == 240 and
                len(summary['source_decodes']) == 4 and
                all(row['passed'] and row['frames'] == 240
                    for row in summary['source_decodes']) and
                'decoded_frames=240' in summary['decoder_stdout'] and
                'full_core=true' in summary['decoder_stdout'] and
                summary['reported_duration_s'] == EXPECTED_SECONDS[candidate] and
                summary['reported_activity_events'] == 0,
                'Full CPU saved proof differs: ' + candidate)
        observed = report['measurements']['signed_curb_observation']['value']
        require(observed['source_kind'] == 'synthetic_native_sample' and
                observed['displayed_sign_classes'] == ['no_parking'] and
                observed['red_curb_stationary_duration_s'] == EXPECTED_SECONDS[candidate] and
                observed['legal_verdict'] is None,
                'Signed source-derived measurement differs: ' + candidate)
        require(compatibility['passed'] is True and
                compatibility['case_id'] == case and
                compatibility['candidate_id'] == candidate and
                compatibility['construction_sha256'] == expected_hash and
                {'selected_measurements', 'negative_case_source', 'four_camera_sources'} <=
                set(compatibility['checks']),
                'Candidate compatibility differs: ' + candidate)
        require(negative['rejected'] is True and
                negative['candidate_id'] == candidate and
                negative['removed'] == 'native-map-readback.json' and
                negative['positive_processing_sha256'] == summary['processing_sha256'],
                'Missing map source accepted: ' + candidate)
        require(config['case_id'] == case and
                config['service_class'] == 'ordinary' and
                config['sign_classes'] == ['no_parking'] and
                config['native_blueprint'] == 'vehicle.tesla.model3',
                'Fixed signed-curb scene differs: ' + candidate)
        configs[candidate] = config
        records.append({'candidate_id': candidate,
                        'construction_sha256': expected_hash,
                        'summary_sha256': sha(ROOT / summary_name),
                        'compatibility_sha256': sha(ROOT / compatibility_name),
                        'negative_sha256': sha(ROOT / negative_name),
                        'duration_s': EXPECTED_SECONDS[candidate]})
    base = configs['primary']
    for candidate in CANDIDATES[1:]:
        different = {key for key in base.keys() | configs[candidate].keys()
                     if base.get(key) != configs[candidate].get(key)}
        require(different <= ALLOWED_CHANGES,
                'Fallback changed fixed scene conditions: ' + candidate)
    require(configs['fallback1']['requested_approach_frames'] >
            base['requested_approach_frames'] and
            configs['fallback3']['requested_approach_frames'] <
            base['requested_approach_frames'] and
            configs['fallback2']['camera_policy'] != base['camera_policy'],
            'Fallback mitigations differ from physical risks')
    return {'format': 'c150142-ordinary-red-saved-audit-v1', 'passed': True,
            'case_id': case, 'candidate_count': 4,
            'distinct_triggers': sorted(triggers), 'records': records,
            'original_native_observed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
