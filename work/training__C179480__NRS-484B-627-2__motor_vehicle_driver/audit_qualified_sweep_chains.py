"""Independent source/identity audit for all qualified sweep CPU chains."""
import hashlib
import json
from pathlib import Path

from control_phase_measurement import measure_red_onset
from sweep_case import resolve

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parents[1] / '.runtime-work/c179480-native-sweep'
REQUIRED_CHECKS = {'acquisition_unchanged', 'actual_analysis',
                   'derived_outputs_rebuilt', 'final_decode', 'four_camera_sources',
                   'lean_decoder', 'mandatory_observations', 'native_validation',
                   'render', 'selected_measurements', 'negative_case_source'}
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'sweep-candidate-manifest.json'
    manifest = read(manifest_path)
    rows = []
    for entry in manifest['cases']:
        cid = entry['case_id']
        if not cid.startswith(HERE.name + '__'):
            raise ValueError('Unqualified case ID: ' + cid)
        candidates = [('primary', entry)] + [(item['id'], item) for item in entry['candidates']]
        for candidate_id, candidate in candidates:
            name = f'{cid}-{candidate_id}'
            attempt = ASSETS / 'compatibility-qualified-v3' / cid / candidate_id
            config = read(attempt / 'config.json')
            _, axis, value = resolve(config)
            construction = HERE / candidate['construction']
            if sha(construction) != candidate['construction_sha256']:
                raise ValueError('Construction changed: ' + name)
            compat_path = HERE / f'sweep-qualified-v3-{name}-compatibility.log'
            saved_path = HERE / f'sweep-qualified-v3-{name}-saved.log'
            compat, saved = read(compat_path), read(saved_path)
            if (not compat['passed'] or compat['case_id'] != cid or
                    compat['candidate_id'] != candidate_id or
                    compat['construction_sha256'] != candidate['construction_sha256'] or
                    compat['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
                    not REQUIRED_CHECKS <= set(compat['checks'])):
                raise ValueError('Compatibility incomplete: ' + name)
            negative = (attempt / 'negative-analysis.log').read_text()
            if (compat['negative_removed'] != 'native-map-readback.json' or
                    compat['negative_error_contains'] not in negative):
                raise ValueError('Missing-source negative did not reject: ' + name)
            if (not saved['passed'] or saved['case_id'] != cid or
                    not saved['recorded_only'] or not saved['originals_preserved'] or
                    saved['timestamp_joins']['frames'] != 600 or
                    not saved['timestamp_joins']['passed'] or saved['missing_evidence'] or
                    saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
                raise ValueError('Recorded-only saved proof incomplete: ' + name)
            if any(not (attempt / camera).is_file() for camera in CAMERAS):
                raise ValueError('Missing four-camera source: ' + name)
            actors = [json.loads(line) for line in
                      (attempt / 'native-actors.jsonl').read_text().splitlines()]
            channel = [json.loads(line) for line in
                       (attempt / 'channels' / (axis + '.jsonl')).read_text().splitlines()]
            if len(actors) != 600 or len(channel) != 600:
                raise ValueError('Sweep source channel lacks 600 joins: ' + name)
            if axis == 'governing_red_onset_s':
                expected = measure_red_onset(
                    attempt / 'native-actors.jsonl', attempt / 'video_frames.jsonl',
                    expected_control_id=read(attempt / 'native-map-readback.json')[
                        'surveyed_governing_traffic_light_id'],
                    source_kind='synthetic_native_sample')['red_onset_s']
                values = [expected] * 600
            elif axis == 'following_gap_m':
                values = [row['following_gap_m'] for row in actors]
            else:
                values = [row['hazard_state']['ego_center_gap_m'] for row in actors]
            if [row['value'] for row in channel] != values:
                raise ValueError('Sweep channel differs from retained actors: ' + name)
            definition = config['sweep_measurement']
            summary = read(attempt / 'result.json')['realized_observables'][axis]
            procedure = definition['measurement']
            measured = min(values) if procedure['statistic'] == 'min' else values[0]
            if (definition['observable'] != axis or definition['variable'] != axis or
                    summary['value'] != measured or
                    summary['reference'] != 'channels/' + axis + '.jsonl' or
                    summary['sample_window_s'] != [channel[0]['time_s'], channel[-1]['time_s']] or
                    any(summary[key] != procedure[key]
                        for key in ('method', 'time_window', 'statistic'))):
                raise ValueError('Frozen realized sweep summary differs from sources: ' + name)
            rows.append({'case_id': cid, 'candidate_id': candidate_id,
                         'axis': axis, 'point': value,
                         'compatibility_log_sha256': sha(compat_path),
                         'saved_log_sha256': sha(saved_path),
                         'actor_source_sha256': sha(attempt / 'native-actors.jsonl')})
    if len(rows) != 36:
        raise ValueError('All 36 qualified sweep candidates required')
    return {'format': 'c179480-independent-qualified-sweep-chain-audit-v1',
            'passed': True, 'case_count': 9, 'candidate_count': 36,
            'manifest_sha256': sha(manifest_path),
            'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
            'rows': rows, 'selected_cases': 0, 'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2, sort_keys=True))
