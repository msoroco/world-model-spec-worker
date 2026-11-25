"""Build explicit, source-shaped CPU diagnostics; no physical acquisition claim."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / 'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver/diagnostic-following_base_probe.json'
ASSIGNMENT = HERE.name
SUFFIXES = ('right_crest_obstructed', 'left_crest_obstructed',
            'left_crest_clear', 'left_one_way_obstructed')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False) + '\n'


def video_hashes(videos):
    output = {}
    with tempfile.TemporaryDirectory(prefix='c104084-video-') as temporary:
        for video in videos:
            target = Path(temporary) / video['path']
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-n', '-f', 'lavfi', '-i',
                f"color=c={video['color']}:s={video['width']}x{video['height']}:r={video['fps']}",
                '-frames:v', str(video['frames']), '-an', '-c:v', 'ffv1',
                '-threads', '1', '-fflags', '+bitexact', '-flags:v', '+bitexact',
                str(target)], check=True, timeout=120)
            output[video['path']] = sha(target.read_bytes())
    return output


def make(suffix, base, movie_hashes):
    case_id = ASSIGNMENT + '__' + suffix
    spec = json.loads(json.dumps(base))
    files = spec['files']
    original_grade = '<elevation s="0" a="0" b="0" c="0" d="0" />'
    diagnostic_grade = '<elevation s="0" a="0" b="0.04" c="-0.0002" d="0" />'
    if files['road.xodr'].count(original_grade) != 1:
        raise ValueError('Diagnostic OpenDRIVE grade anchor changed')
    files['road.xodr'] = files['road.xodr'].replace(original_grade, diagnostic_grade)
    for name in tuple(files):
        if name.startswith(('following-', 'following_', 'surface_', 'alley_',
                            'speed_', 'body_history', 'acquisition.json')):
            files.pop(name)
    capture = json.loads(files['capture/manifest.json'])
    capture['case_id'] = case_id
    capture['source_run'] = 'diagnostic:synthetic-source-shaped-crest'
    capture['diagnostic_fixture'] = True
    capture['physical_acceptance_claimed'] = False
    capture['sources']['road.xodr'] = sha(files['road.xodr'].encode())
    files['capture/manifest.json'] = dump(capture)
    frame_map = [json.loads(line) for line in files['video_frames.jsonl'].splitlines() if line]
    ids = [row['carla_frame'] for row in frame_map]
    left = suffix != 'right_crest_obstructed'
    blocked = suffix != 'left_crest_clear'
    one_way = suffix == 'left_one_way_obstructed'
    body = []
    rays = []
    for row in frame_map:
        frame = row['carla_frame']
        body.append({'frame': frame, 'timestamp_s': row['time_s'],
                     'ego_body_corners_signed_m': [0.7, 0.8, 1.0, 1.1] if left
                     else [-2.1, -1.9, -1.6, -1.4],
                     'opposing_body_distance_m': 30.0 + (frame - ids[0]),
                     'ego_source_ref': 'synthetic:ego-body',
                     'opposing_source_ref': 'synthetic:opposing-body',
                     'opposing_route_index': frame - ids[0],
                     'opposing_body_vertices_m': [[128.0, -1.75, 0.2],
                                                   [130.0, -1.75, 1.8]]})
        rays.append({'frame': frame, 'body_corner_ray_hits': [blocked] * 4,
                     'ray_source_ref': 'synthetic:crest-ray'})
    files['frames.jsonl'] = ''.join(dump(row) for row in body)
    files['crest-rays.jsonl'] = ''.join(dump(row) for row in rays)
    context = {'case_id': case_id, 'law_id': 'NRS-484B-213-2a',
               'lane_allocation': 'one_way' if one_way else 'two_way',
               'highway_source_ref': 'synthetic:highway',
               'center_reference_source_ref': 'synthetic:road-center',
               'opposing_lane_source_ref': None if one_way else 'synthetic:opposing-lane'}
    if one_way:
        authority = {'case_id': case_id, 'source_kind': 'one_way_authority',
                     'source_ref': 'synthetic:one-way-designation',
                     'diagnostic_fixture': True}
        files['one-way-authority.json'] = dump(authority)
        context['one_way_authority'] = {'source_ref': 'synthetic:one-way-designation',
                                        'sha256': sha(files['one-way-authority.json'].encode())}
    files['lane-context.json'] = dump(context)
    files['frame-map.json'] = dump({'frames': ids,
        'camera_frames': {name: ids for name in
            ('overview', 'approach', 'reference_corner', 'driver_reference')}})
    profile = {'case_id': case_id, 'map_opendrive_sha256': sha(files['road.xodr'].encode()),
               'grade_proxy': {'sampled_grade_blocks_proxy_ray': blocked,
                               'method': 'synthetic diagnostic profile only'},
               'diagnostic_fixture': True}
    files['road-profile.json'] = dump(profile)
    files['acquisition-provenance.json'] = dump({
        'diagnostic_fixture': True, 'case_id': case_id,
        'physical_acceptance_claimed': False,
        'scope': 'source-shaped CPU software diagnostic only'})
    names = ('frames.jsonl', 'lane-context.json', 'crest-rays.jsonl',
             'frame-map.json', 'road-profile.json')
    hashes = {name: sha(files[name].encode()) for name in names}
    hashes.update(movie_hashes)
    if one_way:
        hashes['one-way-authority.json'] = sha(files['one-way-authority.json'].encode())
    files['source-hashes.json'] = dump(hashes)
    files['original-hashes.json'] = dump(hashes)
    files['fixture-provenance.json'] = dump({
        'diagnostic_fixture': True, 'case_id': case_id,
        'physical_acceptance_claimed': False,
        'source_shape': 'original 9-frame graph, trace and four FFV1 views plus synthetic crest packets'})
    return spec


def main():
    base = json.loads(BASE.read_text())
    movies = video_hashes(base['videos'])
    for suffix in SUFFIXES:
        spec = make(suffix, base, movies)
        spec_path = HERE / f'diagnostic-{suffix}.json'
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, sort_keys=True) + '\n')
        input_path = REPO / 'inputs' / ASSIGNMENT / 'assignment.json'
        recipe = {'format': 'worker-fixture-recipe', 'sources': [{
            'path': 'diagnostic-input.json',
            'source': str(input_path.relative_to(REPO)),
            'sha256': sha(input_path.read_bytes())}], 'generator': {
            'source': str(spec_path.relative_to(REPO)),
            'sha256': sha(spec_path.read_bytes())}}
        (HERE / f'diagnostic-{suffix}-recipe.json').write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + '\n')
        print(suffix, spec_path.stat().st_size, recipe['generator']['sha256'])


if __name__ == '__main__':
    main()
