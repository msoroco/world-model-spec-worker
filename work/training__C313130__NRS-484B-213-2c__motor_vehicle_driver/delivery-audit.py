"""Independently join saved tunnel diagnostics; reject unobserved Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ERROR = 'Original tunnel identity, obstructed view and four camera pixels required for delivery acceptance'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Select one exact case')
    if not diagnostic:
        raise ValueError(ERROR)
    suffix = case_id.rsplit('__', 1)[-1]
    source = HERE / 'fixture-source' / suffix
    joined = [rows(source / name) for name in ('tunnel-rows.jsonl', 'trace.jsonl',
        'video_frames.jsonl', 'capture/evidence.jsonl', 'vehicle-extents.jsonl',
        'sight-rays.jsonl')]
    if any(len(group) != 600 for group in joined):
        raise ValueError('Incomplete 600-frame source join')
    for index, group in enumerate(zip(*joined)):
        if (group[0].get('native_frame') != index or group[1].get('frame') != index or
                group[2].get('native_frame') != index or group[3].get('original_frame') != index or
                group[4].get('native_frame') != index or group[5].get('native_frame') != index or
                abs(group[0]['time_s'] - group[1]['time_s']) > 1e-6 or
                abs(group[0]['time_s'] - group[2]['time_s']) > 1e-6):
            raise ValueError('Tunnel, trace and video frame join differs')
    public_path = HERE / 'selected-proofs' / (suffix + '-primary-compatibility.json')
    saved_path = HERE / 'selected-proofs' / (suffix + '-primary-processing.json')
    public = json.loads(public_path.read_text())
    saved = json.loads(saved_path.read_text())
    if (public['case_id'] != case_id or public['construction_sha256'] != entry['construction_sha256'] or
            not public['passed'] or not {'four_camera_sources', 'lean_decoder', 'final_decode',
                'selected_measurements', 'negative_case_source'} <= set(public['checks'])):
        raise ValueError('Selected public proof incomplete')
    if (saved['case_id'] != case_id or not saved['passed'] or not saved['recorded_only'] or
            not saved['originals_preserved'] or saved['physical_acceptance_claimed'] or
            saved['legal_acceptance_claimed']):
        raise ValueError('Recorded-only saved proof incomplete')
    measured = public['measurement_examples']['tunnel_approach']['value']
    expected = 0 if suffix == 'probe_1' else 153
    if (measured['within_100_ft_driving_frames'] != 153 or
            measured['blocked_sight_within_zone_frames'] != 153 or
            measured['left_and_blocked_within_zone_frames'] != expected):
        raise ValueError('Source-derived tunnel interval differs')
    return {'case_id': case_id, 'joined_frames': 600, 'diagnostic_only': True,
        'original_native_observed': False, 'physical_acceptance': False, 'legal_verdict': None,
        'left_and_blocked_frames': expected, 'source_sha256': sha(source / 'tunnel-rows.jsonl'),
        'compatibility_sha256': sha(public_path), 'saved_sha256': sha(saved_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
