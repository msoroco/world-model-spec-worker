"""Independent source and receipt audit for selected CPU delivery diagnostics.

This audits synthetic source shape and software proof, not physical acceptance.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case, remove_native_source=False):
    manifest = read(HERE / 'current-base-proof-manifest.json')
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    suffix = case.rsplit('__', 1)[-1]
    letter = {'false': 'a', 'true': 'b'}[suffix]
    spec_path = HERE / f'selected-diagnostic-condition_{letter}.json'
    recipe_path = HERE / f'selected-diagnostic-condition_{letter}-recipe.json'
    spec = read(spec_path)
    if read(recipe_path)['generator']['sha256'] != sha(spec_path):
        raise ValueError('Selected recipe/source hash differs')
    files = spec['files']
    if remove_native_source:
        files.pop('native_samples.jsonl', None)
    required = ('native_samples.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                'body_history.jsonl', 'capture/evidence.jsonl', 'capture/manifest.json',
                'road_geometry.json')
    for name in required:
        if name not in files:
            raise ValueError('Missing required source: ' + name)
    rows = {name: [json.loads(line) for line in files[name].splitlines()]
            for name in required if name.endswith('.jsonl')}
    if any(len(v) != 840 for v in rows.values()):
        raise ValueError('Source participant/frame count differs')
    for i, (native, trace, mapping, body, evidence) in enumerate(zip(
            rows['native_samples.jsonl'], rows['trace.jsonl'], rows['video_frames.jsonl'],
            rows['body_history.jsonl'], rows['capture/evidence.jsonl'])):
        frame = 100 + i
        if (native['native_frame'] != frame or trace['frame'] != frame
                or mapping['native_frame'] != frame or mapping['video_frame'] != i
                or body['frame'] != frame or evidence['original_frame'] != frame):
            raise ValueError('Original frame join differs')
        time = (i + 1) / 20
        if any(abs(float(t) - time) > 1e-6 for t in
               (native['time_s'], trace['time_s'], mapping['time_s'],
                body['time_s'], evidence['recording_time_s'])):
            raise ValueError('Original time join differs')
        vertices = native['native_body_xy_m']
        source_xy = {(round(v[0], 4), round(v[1], 4)) for v in vertices}
        body_xy = {(round(v[0], 4), round(v[1], 4)) for v in body['body_vertices_m']}
        evidence_xy = {(round(v[0], 4), round(v[1], 4)) for v in evidence['ego']['body_vertices_m']}
        if (len(vertices) != 4 or len(body['body_vertices_m']) != 8
                or len(evidence['ego']['body_vertices_m']) != 8
                or source_xy != body_xy or source_xy != evidence_xy):
            raise ValueError('Original full body differs')
    compat_path = HERE / f'atom-fixed-{suffix}-primary-compatibility-receipt.json'
    saved_path = HERE / f'atom-fixed-{suffix}-primary-saved-receipt.json'
    compat, saved = read(compat_path), read(saved_path)
    sample_sha = hashlib.sha256(files['native_samples.jsonl'].encode()).hexdigest()
    if (not compat['passed'] or compat['case_id'] != case
            or compat['construction_sha256'] != entry['construction_sha256']
            or compat['fixture_recipe_sha256'] != sha(recipe_path)
            or compat['fixture_manifest']['native_samples.jsonl'] != sample_sha
            or compat['negative_error_contains'] != 'Missing required source: native_samples.jsonl'):
        raise ValueError('Compatibility/source binding differs')
    if {name + '.mkv' for name in CAMERAS} - set(compat['fixture_manifest']):
        raise ValueError('Four source camera bindings missing')
    result = saved['result']
    final_path = HERE / f'atom-fixed-{suffix}-primary-result.json'
    final_result = read(final_path)
    if (saved['source']['fixture_sha256'] != compat['fixture_sha256']
            or result['case_id'] != case or result['candidate_id'] != 'primary'
            or result['result_sha256'] != sha(final_path)
            or result['analysis_revision']['construction_sha256'] != entry['construction_sha256']
            or not result['recorded_only'] or not result['originals_preserved']
            or result['missing_evidence'] or not result['final_video_checks']['passed']
            or result['final_video_checks']['frames'] != 840
            or result['physical_acceptance_claimed'] or result['legal_acceptance_claimed']):
        raise ValueError('Saved processing/source binding differs')
    motion = rows['native_samples.jsonl']
    reverse = [x for x in motion if x['signed_forward_velocity_m_s'] < -0.05]
    heading = max(abs((x['heading_deg'] - motion[0]['heading_deg'] + 180) % 360 - 180)
                  for x in reverse)
    expected = 'backing_around_street_corner' if suffix == 'true' else 'backing_straight_through_intersection'
    if (len(reverse) < 20 or (heading >= 30) != (suffix == 'true')
            or final_result['measured_values']['relation'] != expected):
        raise ValueError('Independent reverse/corner outcome differs')
    return {'passed': True, 'case_id': case, 'source_frames': 840,
            'reverse_frames': len(reverse), 'max_reverse_heading_deg': heading,
            'four_camera_source_hashes': True, 'full_final_decode_receipt': True,
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'scope': 'synthetic CPU source/receipt audit; actual pixels and physical completion require local capture',
            'accepted': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_native_source), indent=2))
