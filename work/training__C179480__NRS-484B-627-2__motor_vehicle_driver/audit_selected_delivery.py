"""Independent CPU source and receipt audit for one C179480 delivery case.

Synthetic fixture/video proof establishes software readiness only. Actual
Native pixels, physical completion and statutory judgments remain local review.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case_id, remove_native_source=False):
    manifest = read(HERE / 'execution-manifest.json')
    entries = [row for row in manifest['cases'] if row['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Unknown selected exact case')
    entry = entries[0]
    recipe = read(ROOT / entry['fixture_recipe'])
    generator = ROOT / recipe['generator']['source']
    if sha(generator) != recipe['generator']['sha256']:
        raise ValueError('Diagnostic generator changed')
    source = {item['path']: item for item in recipe['sources']}
    if remove_native_source:
        source.pop('native-actors.jsonl', None)
    required = ('native-actors.jsonl', 'video_frames.jsonl', 'native-map-readback.json')
    for name in required:
        if name not in source:
            raise ValueError('Missing required source: ' + name)
    for item in source.values():
        if sha(ROOT / item['source']) != item['sha256']:
            raise ValueError('Retained source hash changed: ' + item['path'])
    actors = [json.loads(line) for line in (ROOT / source['native-actors.jsonl']['source']).read_text().splitlines()]
    mapping = [json.loads(line) for line in (ROOT / source['video_frames.jsonl']['source']).read_text().splitlines()]
    if len(actors) != 600 or len(mapping) != 600:
        raise ValueError('All 600 original source/frame rows required')
    if any(actor['frame'] != frame['carla_frame'] or
           actor['video_frame'] != frame['video_frame'] or
           abs(frame['time_s'] - index / 20) > 1e-9
           for index, (actor, frame) in enumerate(zip(actors, mapping))):
        raise ValueError('Original actor/frame time join differs')
    participants = ('ego_x_m', 'ego_y_m', 'ego_speed_mps',
                    'following_x_m', 'following_speed_mps')
    if any(any(key not in actor for key in participants) for actor in actors):
        raise ValueError('Original ego/follower participant source missing')
    compat_spec = entry.get('compatibility', {})
    saved_spec = entry.get('saved_processing', {})
    if not all(key in compat_spec for key in ('receipt', 'sha256', 'log', 'negative_log')):
        raise ValueError('Exact primary compatibility receipt missing')
    if not all(key in saved_spec for key in ('receipt', 'sha256')):
        raise ValueError('Exact recorded-only saved receipt missing')
    compat_path, saved_path = HERE / compat_spec['receipt'], HERE / saved_spec['receipt']
    if sha(compat_path) != compat_spec['sha256'] or sha(saved_path) != saved_spec['sha256']:
        raise ValueError('Returned CPU receipt hash changed')
    compat, saved = read(compat_path), read(saved_path)
    if (not compat['passed'] or compat['case_id'] != case_id or
            compat['candidate_id'] != 'primary' or
            compat['construction_sha256'] != entry['construction_sha256'] or
            compat['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
            compat['fixture_recipe_sha256'] != sha(ROOT / entry['fixture_recipe']) or
            not {'negative_case_source', 'native_validation', 'final_decode',
                 'four_camera_sources', 'selected_measurements'} <= set(compat['checks'])):
        raise ValueError('Exact positive/negative compatibility differs')
    if {name for name in CAMERAS} - set(compat['fixture_manifest']):
        raise ValueError('Four named source cameras missing')
    negative = (HERE / compat_spec['negative_log']).read_text()
    if (compat['negative_removed'] != 'native-map-readback.json' or
            compat['negative_error_contains'] not in negative):
        raise ValueError('Missing-source negative did not reject')
    if (not saved['passed'] or saved['case_id'] != case_id or
            saved['candidate_id'] != 'primary' or not saved['recorded_only'] or
            not saved['originals_preserved'] or saved['missing_evidence'] or
            saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed'] or
            saved['analysis_revision']['construction_sha256'] != entry['construction_sha256'] or
            not saved['timestamp_joins']['passed'] or saved['timestamp_joins']['frames'] != 600 or
            not saved['final_video_checks']['passed'] or saved['final_video_checks']['frames'] != 600):
        raise ValueError('Recorded-only saved source/video proof incomplete')
    physical = read(HERE / entry['physical_preparation']['receipt'])
    if (sha(HERE / entry['physical_preparation']['receipt']) != entry['physical_preparation']['sha256'] or
            physical['construction_sha256'] != entry['construction_sha256'] or
            {item['kind'] for item in physical['fixtures']} !=
            {'complete_motion', 'incomplete_motion', 'missing_evidence'} or
            physical['actual_native_or_legal_acceptance_claimed']):
        raise ValueError('Synthetic physical outcome contract differs')
    return {'passed': True, 'case_id': case_id, 'source_frames': 600,
            'four_camera_source_hashes': True, 'full_final_decode_receipt': True,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'scope': 'synthetic CPU source/receipt audit; actual pixels, physical completion and law require local capture',
            'accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_native_source), indent=2, sort_keys=True))
