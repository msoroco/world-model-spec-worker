"""Independent selected-source join audit; original acceptance needs Native capture."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED = {'native_source', 'all_participants', 'time_join',
            'full_video_decode', 'actual_pixels', 'physical_completion'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case_id), None)
    if entry is None or entry['kind'] != 'delivery':
        raise ValueError('Select one exact delivery case')
    if not diagnostic:
        raise ValueError('Original Native two-actor body passage and four camera pixels required for delivery acceptance')
    number = case_id.rsplit('_', 1)[-1]
    root = HERE / f'current-v2-probe-{number}-fixture'
    names = {'native': 'native_samples.jsonl', 'evidence': 'capture/evidence.jsonl',
             'trace': 'trace.jsonl', 'frames': 'video_frames.jsonl',
             'native_frames': 'capture/native/frames.jsonl'}
    material = {key: rows(root / name) for key, name in names.items()}
    if any(len(value) != 600 for value in material.values()):
        raise ValueError('Incomplete 600-frame original source join')
    for i, (native, world, motion, frame, original) in enumerate(zip(*material.values())):
        expected = 100 + i
        if (native['video_frame'] != i or native['native_frame'] != expected
                or world['original_frame'] != expected or motion['frame'] != expected
                or frame['native_frame'] != expected or frame['video_frame'] != i
                or original['frame'] != expected
                or any(abs(row['time_s'] - i / 20) > 1e-6 for row in (native, motion, frame, original))
                or abs(world['recording_time_s'] - i / 20) > 1e-6):
            raise ValueError('Native, two-actor, evidence, trace and camera frame/time join differs')
        if not native.get('through') or not native.get('entrant'):
            raise ValueError('Missing participant in source join')
    source_manifest = json.loads((root / 'diagnostic-source-manifest.json').read_text())
    if source_manifest['case_id'] != case_id or source_manifest['source_kind'] != 'synthetic_native_sample':
        raise ValueError('Wrong diagnostic source identity')
    for name in ('road.xodr', 'native_samples.jsonl'):
        if source_manifest['sha256'].get(name) != sha(root / name):
            raise ValueError('Source manifest changed: ' + name)
    public_path = HERE / entry['compatibility']['receipt']
    public = json.loads(public_path.read_text())
    if (sha(public_path) != entry['compatibility']['sha256']
            or public['case_id'] != case_id
            or public['construction_sha256'] != entry['construction_sha256']
            or not public['passed']
            or not {'four_camera_sources', 'lean_decoder', 'final_decode',
                    'selected_measurements', 'negative_case_source'} <= set(public['checks'])):
        raise ValueError('Selected public proof incomplete')
    saved_path = HERE / entry['saved_processing']['receipt']
    saved = json.loads(saved_path.read_text())
    if (sha(saved_path) != entry['saved_processing']['sha256']
            or not saved['processing_receipt']['recorded_only']
            or not saved['source_hashes_preserved']
            or saved['physical_acceptance_claimed'] or saved['legal_verdict_claimed']):
        raise ValueError('Selected recorded-only source preservation incomplete')
    physical = json.loads((HERE / entry['physical_preparation']['receipt']).read_text())
    if (physical['case_id'] != case_id or physical['construction_sha256'] != entry['construction_sha256']
            or {f['kind'] for f in physical['fixtures']}
            != {'complete_motion', 'incomplete_motion', 'missing_evidence'}):
        raise ValueError('Physical CPU fixture proof incomplete')
    return {'case_id': case_id, 'joined_frames': 600,
            'required_checks': sorted(REQUIRED), 'diagnostic_only': True,
            'original_native_observed': False, 'physical_acceptance': False,
            'legal_verdict': None,
            'source_sha256': {key: sha(root / path) for key, path in names.items()},
            'compatibility_sha256': sha(public_path), 'saved_sha256': sha(saved_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))


if __name__ == '__main__':
    main()
