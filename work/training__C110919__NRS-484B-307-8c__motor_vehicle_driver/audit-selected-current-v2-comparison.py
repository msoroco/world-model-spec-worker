"""Independently audit selected 8c same-map halt versus rolling comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    comparison = plan['comparisons'][0]
    if len(manifest['cases']) != 2 or set(comparison['case_ids']) != {e['case_id'] for e in manifest['cases']}:
        raise ValueError('Selected pair differs from frozen comparison')
    results = []
    for suffix in ('probe_a', 'probe_b'):
        case_id = HERE.name + '__' + suffix
        entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
        saved = json.loads((HERE / 'current-v2-candidates' / suffix / 'primary/saved-proof.json').read_text())
        public = json.loads((HERE / 'current-v2-candidates' / suffix / 'primary/compatibility.json').read_text())
        if (not saved['passed'] or not saved['source_hashes_preserved']
                or saved['construction_sha256'] != entry['construction_sha256']
                or saved['compatibility_sha256'] != sha(HERE / 'current-v2-candidates' / suffix / 'primary/compatibility.json')
                or not public['passed'] or public['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
            raise ValueError('Selected primary source chain changed')
        folder = HERE / f'current-v2-{suffix}-fixture'
        native = rows(folder / 'native_samples.jsonl')
        mapping = rows(folder / 'video_frames.jsonl')
        traffic = rows(folder / 'other_traffic_history.jsonl')
        if len(native) != len(mapping) or len(native) != len(traffic) or len(native) != 600:
            raise ValueError('Source frame count differs')
        for index, (sample, frame, other) in enumerate(zip(native, mapping, traffic)):
            if (sample['native_frame'] != frame['carla_frame']
                    or other['native_frame'] != sample['native_frame']
                    or abs(sample['time_s'] - frame['time_s']) > 1e-8
                    or abs(sample['time_s'] - other['time_s']) > 1e-8):
                raise ValueError('Source frame/time join differs')
        measured = public['measurement_examples']['red_right_turn_permission']['value']
        expected = suffix == 'probe_a'
        if (measured['pre_turn_full_halt'] is not expected
                or measured['pre_crossing_stationary_frames'] != (30 if expected else 0)
                or measured['steady_red_frames'] != 600
                or measured['pedestrian_clearance_s'] != 4.55
                or measured['other_traffic_clearance_s'] != 4.8):
            raise ValueError('Measured controlled contrast differs')
        results.append({'case_id': case_id, 'construction_sha256': entry['construction_sha256'],
                        'fixture_source_sha256': {
                            'road_geometry.json': sha(folder / 'road_geometry.json'),
                            'other_traffic_history.jsonl': sha(folder / 'other_traffic_history.jsonl')},
                        'signal_states': [row['signal_state_observed'] for row in native],
                        'walker_conflict': [row['walker_conflict_occupied'] for row in native],
                        'halt': expected, 'stationary_frames': measured['pre_crossing_stationary_frames']})
    if (results[0]['fixture_source_sha256'] != results[1]['fixture_source_sha256']
            or results[0]['signal_states'] != results[1]['signal_states']
            or results[0]['walker_conflict'] != results[1]['walker_conflict']):
        raise ValueError('Fixed source conditions differ')
    receipt = {'format': 'c110919-8c-selected-comparison-audit', 'passed': True,
               'execution_manifest_sha256': sha(manifest_path),
               'candidate_matrix_audit_sha256': sha(HERE / 'current-v2-candidate-matrix-audit.json'),
               'case_ids': comparison['case_ids'],
               'controlled_difference': 'source-measured 30 versus zero stationary frames before right turn under steady red',
               'fixed_road_geometry_sha256': results[0]['fixture_source_sha256']['road_geometry.json'],
               'fixed_other_traffic_sha256': results[0]['fixture_source_sha256']['other_traffic_history.jsonl'],
               'fixed_signal_and_pedestrian_source_rows': 600,
               'original_native_observed': False, 'physical_acceptance_claimed': False,
               'legal_verdict_claimed': False}
    target = HERE / 'current-selected-comparison-audit.json'
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target), 'stationary_frames': [30, 0]}))


if __name__ == '__main__':
    run()
