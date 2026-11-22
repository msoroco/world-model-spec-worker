"""Independent synthetic source audit for the unselected lawful control design."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def box_overlap(vertices, polygon):
    vx, vy = [v[0] for v in vertices], [v[1] for v in vertices]
    px, py = [v[0] for v in polygon], [v[1] for v in polygon]
    return max(0, min(max(vx), max(px)) - max(min(vx), min(px))) * max(
        0, min(max(vy), max(py)) - max(min(vy), min(py)))


def audit(drop_native=False):
    manifest = read(HERE / 'current-runtime-reproof-manifest.json')
    case = next(e for e in manifest['cases'] if e['case_id'].endswith('__control'))
    recipe = read(HERE / 'selected-diagnostic-condition_c-recipe.json')
    source_path = HERE / 'selected-diagnostic-condition_c.json'
    if recipe['generator']['sha256'] != sha(source_path):
        raise ValueError('Control source recipe changed')
    source = read(source_path)['files']
    if drop_native:
        source.pop('native_samples.jsonl', None)
    if 'native_samples.jsonl' not in source:
        raise ValueError('Missing required source: native_samples.jsonl')
    names = ('native_samples.jsonl', 'trace.jsonl', 'body_history.jsonl',
             'video_frames.jsonl', 'capture/evidence.jsonl')
    rows = {name: [json.loads(line) for line in source[name].splitlines()] for name in names}
    if any(len(rowset) != 840 for rowset in rows.values()):
        raise ValueError('Control source frame count differs')
    backing, max_junction, max_crosswalk = 0, 0, 0
    for i, (native, trace, body, mapping, evidence) in enumerate(zip(*(rows[n] for n in names))):
        frame = 100 + i
        if (native['native_frame'] != frame or trace['frame'] != frame
                or body['frame'] != frame or mapping['native_frame'] != frame
                or mapping['video_frame'] != i or evidence['original_frame'] != frame):
            raise ValueError('Control original frame join differs')
        if any(abs(t - (i + 1) / 20) > 1e-6 for t in
               (native['time_s'], trace['time_s'], body['time_s'], mapping['time_s'],
                evidence['recording_time_s'])):
            raise ValueError('Control original time join differs')
        vertices = native['native_body_xy_m']
        xy = {(round(v[0], 4), round(v[1], 4)) for v in vertices}
        if (len(vertices) != 4 or xy != {(round(v[0], 4), round(v[1], 4))
                                            for v in body['body_vertices_m']}
                or xy != {(round(v[0], 4), round(v[1], 4))
                           for v in evidence['ego']['body_vertices_m']}):
            raise ValueError('Control full body differs')
        if native['signed_forward_velocity_m_s'] < -0.05:
            backing += 1
            max_junction = max(max_junction, box_overlap(vertices, native['intersection_polygon_xy_m']))
            max_crosswalk = max(max_crosswalk, box_overlap(vertices, native['crosswalk_polygon_xy_m']))
    if backing < 20 or max_junction or max_crosswalk:
        raise ValueError('Control reverse body enters prohibited geometry')
    for candidate in (case, *case['candidates']):
        path = HERE / candidate['construction']
        if sha(path) != candidate['construction_sha256']:
            raise ValueError('Control construction hash differs')
        bundle = read(path)
        config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
        if (bundle['case_id'] != case['case_id'] or config['duration_s'] != 42
                or config['rate_hz'] != 20 or config['case_suffix'] != 'condition_c'
                or len(config['cameras']) != 4):
            raise ValueError('Control candidate capture contract differs')
    compatibility = read(HERE / 'current-runtime-control-primary-compatibility.json')
    saved = read(HERE / 'current-runtime-control-primary-saved-receipt.json')['result']
    result_path = HERE / 'current-runtime-control-primary-result.json'
    final = read(result_path)
    sample_sha = hashlib.sha256(source['native_samples.jsonl'].encode()).hexdigest()
    if (not compatibility['passed'] or compatibility['case_id'] != case['case_id']
            or compatibility['construction_sha256'] != case['construction_sha256']
            or compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']
            or compatibility['fixture_manifest']['native_samples.jsonl'] != sample_sha
            or not {'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'}
            <= set(compatibility['fixture_manifest'])):
        raise ValueError('Control compatibility source/receipt differs')
    if (not saved['passed'] or not saved['recorded_only'] or not saved['originals_preserved']
            or saved['missing_evidence'] or saved['physical_acceptance_claimed']
            or saved['legal_acceptance_claimed'] or saved['result_sha256'] != sha(result_path)
            or saved['analysis_revision']['construction_sha256'] != case['construction_sha256']
            or not saved['final_video_checks']['passed']
            or saved['final_video_checks']['frames'] != 840
            or final['measured_values']['relation'] != 'backing_clear_of_intersection'
            or final['measured_values']['max_backing_intersection_overlap_m2'] != 0):
        raise ValueError('Control saved processing/clear-body outcome differs')
    return {'passed': True, 'case_id': case['case_id'], 'source_frames': 840,
            'reverse_frames': backing, 'max_intersection_box_overlap_m2': max_junction,
            'max_crosswalk_box_overlap_m2': max_crosswalk, 'candidate_bundles': 4,
            'four_camera_source_hashes': True, 'full_final_decode_receipt': True,
            'scope': 'authored synthetic control only; Native road/body and pixels remain unverified'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--drop-native', action='store_true')
    args = parser.parse_args()
    expected = json.loads((HERE / 'current-runtime-reproof-manifest.json').read_text())['cases'][-1]['case_id']
    if args.case != expected or not expected.endswith('__control'):
        raise ValueError('Control audit selected another case')
    print(json.dumps(audit(args.drop_native), indent=2))
