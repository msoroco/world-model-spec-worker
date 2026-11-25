"""Independently audit selected island-side joins and reject Native acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check(case_id, diagnostic):
    manifest = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Select one exact case')
    if not diagnostic:
        raise ValueError('Original physical island, body passage and four camera pixels required for delivery acceptance')
    suffix = case_id.rsplit('__', 1)[-1]
    source = HERE / 'selected-source' / suffix
    native = rows(source / 'native-raw-actors.jsonl')
    evidence = rows(source / 'capture/evidence.jsonl')
    trace = rows(source / 'trace.jsonl')
    video = rows(source / 'video_frames.jsonl')
    if any(len(x) != 600 for x in (native, evidence, trace, video)):
        raise ValueError('Incomplete 600-frame source join')
    for index, (actor, world, motion, frame) in enumerate(zip(native, evidence, trace, video)):
        expected = 100 + index
        if (actor['native_frame'] != expected or world['original_frame'] != expected or
                motion['frame'] != expected or frame['native_frame'] != expected or
                abs(actor['time_s'] - frame['time_s']) > 1e-6 or
                actor['ego']['center_native_xyz_m'] != world['ego']['position_m']):
            raise ValueError('Native/source body, frame or time join differs')
    compatibility = HERE / 'selected-proofs' / f'{suffix}-primary-compatibility.json'
    saved_path = HERE / 'selected-proofs' / f'{suffix}-primary-processing.json'
    public = json.loads(compatibility.read_text())
    saved = json.loads(saved_path.read_text())
    if (public['case_id'] != case_id or public['construction_sha256'] != entry['construction_sha256'] or
            not public['passed'] or not {'four_camera_sources', 'lean_decoder', 'final_decode',
                                         'selected_measurements', 'negative_case_source'} <= set(public['checks'])):
        raise ValueError('Selected public proof incomplete')
    if (not saved['passed'] or not saved['recorded_only'] or not saved['originals_preserved'] or
            saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
        raise ValueError('Recorded-only saved proof incomplete')
    observed = public['measurement_examples']['island_side_observation']['value']
    expected = 'left' if suffix == 'reference' else 'right'
    if observed['island_side_frame_counts'][expected] != 600 or observed['physical_island_verified']:
        raise ValueError('Source-derived island side or physical status differs')
    return {'case_id': case_id, 'joined_frames': 600, 'diagnostic_only': True,
            'original_native_observed': False, 'physical_acceptance': False,
            'legal_verdict': None, 'source_sha256': sha(source / 'native-raw-actors.jsonl'),
            'source_derived_island_side': expected, 'physical_island_verified': False,
            'compatibility_sha256': sha(compatibility), 'saved_sha256': sha(saved_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
