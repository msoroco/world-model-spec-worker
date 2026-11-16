"""Independently audit pinned synthetic below-boundary fallback evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__tour_bus_below'
PREFIX = 'c150142-tour-bus-pinned-saved-below-'
ALLOWED_CONFIG_CHANGES = {'candidate_id', 'risk_trigger', 'requested_target_x_m',
                          'camera_policy', 'tracks_sha256'}
FIXED = {'capture_frames': 36120, 'requested_approach_frames': 120,
         'requested_stationary_duration_s': 1799.95,
         'requested_boundary': 'below', 'rate_hz': 20}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit():
    manifest = read(ROOT / 'execution-manifest-diagnostic-tour_bus_below-draft.json')
    entry = next(e for e in manifest['cases'] if e['case_id'] == CASE)
    fallback_entries = {c['id']: c for c in entry['candidates']}
    require(set(fallback_entries) == {'fallback1', 'fallback2', 'fallback3'},
            'Expected exactly three source-bound fallback candidates')
    triggers = {(c['trigger']['metric'], c['trigger']['failure_condition'])
                for c in fallback_entries.values()}
    require(len(triggers) == 3, 'Fallback physical-risk triggers overlap')
    records = []
    configs = {}
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        stem = ('result-v7' if candidate == 'primary' else candidate + '-result-v1')
        version = REPO / '.runtime-work' / (PREFIX + stem) / 'v0001'
        summary_name = ('update032-below-primary-pinned-saved-recheck.json'
                        if candidate == 'primary' else
                        f'update032-below-{candidate}-pinned-saved-v1.json')
        summary = read(ROOT / summary_name)
        processing = read(version / 'processing.json')
        selected = read(version / 'analysis/candidate-selection.json')
        negative = read(ROOT / f'update032-below-{candidate}-negative.json')
        config = read(version / 'analysis/config.json')
        expected_sha = (entry['construction_sha256'] if candidate == 'primary'
                        else fallback_entries[candidate]['construction_sha256'])
        require(processing['passed'] is True and
                processing['candidate_id'] == selected['candidate_id'] == candidate and
                processing['analysis_revision']['construction_sha256'] ==
                selected['construction_sha256'] == expected_sha,
                'Pinned candidate identity differs: ' + candidate)
        require(summary['processing_sha256'] == sha(version / 'processing.json') and
                summary['processing_passed'] is True and
                summary['timestamp_join_frames'] == summary['final_decode_frames'] == 36120 and
                summary['reported_duration_s'] == 1799.95 and
                summary['reported_boundary'] == 'below' and
                summary['reported_activity_events'] == 1 and
                len(summary['source_decodes']) == 4 and
                all(s['passed'] and s['frames'] == 36120 for s in summary['source_decodes']) and
                'full_core=true' in summary['decoder_stdout'],
                'Full pinned CPU proof differs: ' + candidate)
        require(negative['rejected'] is True and
                negative['candidate_id'] == candidate and
                negative['positive_processing_sha256'] == summary['processing_sha256'] and
                negative['removed'] == 'native-map-readback.json',
                'Missing-source rejection differs: ' + candidate)
        require(all(config.get(k) == v for k, v in FIXED.items()) and
                config['case_id'] == CASE,
                'Fixed law-boundary configuration differs: ' + candidate)
        configs[candidate] = config
        records.append({'candidate_id': candidate,
                        'construction_sha256': expected_sha,
                        'processing_sha256': summary['processing_sha256'],
                        'summary_sha256': sha(ROOT / summary_name),
                        'negative_sha256': sha(ROOT / f'update032-below-{candidate}-negative.json'),
                        'target_x_m': config['requested_target_x_m'],
                        'camera_policy': config['camera_policy']})
    base = configs['primary']
    for candidate in fallback_entries:
        changed = {key for key in base.keys() | configs[candidate].keys()
                   if base.get(key) != configs[candidate].get(key)}
        require(changed <= ALLOWED_CONFIG_CHANGES and changed &
                {'requested_target_x_m', 'camera_policy'},
                'Fallback changes fixed scenario conditions: ' + candidate)
    require(configs['fallback1']['requested_target_x_m'] < base['requested_target_x_m'] <
            configs['fallback3']['requested_target_x_m'] and
            configs['fallback2']['camera_policy'] != base['camera_policy'],
            'Fallback mitigations do not match physical-risk triggers')
    return {'format': 'c150142-tour-bus-below-fallback-audit-v1',
            'source_kind': 'synthetic_native_sample',
            'original_native_observed': False, 'passed': True,
            'case_id': CASE, 'records': records,
            'distinct_triggers': sorted(triggers)}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
