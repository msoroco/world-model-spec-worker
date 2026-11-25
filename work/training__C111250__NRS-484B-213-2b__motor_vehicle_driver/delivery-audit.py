"""Audit selected saved intersection sources and reject original acceptance absent Native capture."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAME = {'probe_01': 'primary', 'probe_02': 'contrast', 'probe_03': 'traversal'}


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
        raise ValueError('Original physical highway, body passage and four camera pixels required for delivery acceptance')
    suffix = case_id.rsplit('__', 1)[-1]
    source = HERE / f'current-v2-{NAME[suffix]}-sources'
    bodies = rows(source / 'vehicle-footprints.jsonl')
    evidence = rows(source / 'capture/evidence.jsonl')
    trace = rows(source / 'trace.jsonl')
    video = rows(source / 'video_frames.jsonl')
    if any(len(item) != 600 for item in (bodies, evidence, trace, video)):
        raise ValueError('Incomplete 600-frame source join')
    for index, (body, world, motion, frame) in enumerate(zip(bodies, evidence, trace, video)):
        if (body['native_frame'] != index or motion['frame'] != index or
                frame['native_frame'] != index or abs(body['time_s'] - frame['time_s']) > 1e-6):
            raise ValueError('Body, trace and video frame/time join differs')
    public_path = HERE / 'selected-proofs' / f'{suffix}-primary-compatibility.json'
    saved_path = HERE / 'selected-proofs' / f'{suffix}-primary-processing.json'
    public = json.loads(public_path.read_text())
    saved = json.loads(saved_path.read_text())
    if (public['case_id'] != case_id or public['construction_sha256'] != entry['construction_sha256'] or
            not public['passed'] or not {'four_camera_sources', 'lean_decoder', 'final_decode',
                                         'selected_measurements', 'negative_case_source'} <= set(public['checks'])):
        raise ValueError('Selected public proof incomplete')
    if (not saved['passed'] or not saved['recorded_only'] or not saved['originals_preserved'] or
            saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
        raise ValueError('Recorded-only saved proof incomplete')
    measured = public['measurement_examples']['zone_measurement']['value']
    expected = {'probe_01': (None, None), 'probe_02': (240, 358),
                'probe_03': (None, 400)}[suffix]
    if (measured['first_left_approach_frame'], measured['first_left_traversal_frame']) != expected:
        raise ValueError('Source-derived temporal interval differs')
    return {'case_id': case_id, 'joined_frames': 600, 'diagnostic_only': True,
            'original_native_observed': False, 'physical_acceptance': False,
            'legal_verdict': None, 'source_sha256': sha(source / 'vehicle-footprints.jsonl'),
            'source_derived_left_frames': expected,
            'compatibility_sha256': sha(public_path), 'saved_sha256': sha(saved_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
