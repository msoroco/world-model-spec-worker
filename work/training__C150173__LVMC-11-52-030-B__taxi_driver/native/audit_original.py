"""Independent original-source audit for the taxi yellow-zone attempt."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

VIEWS = {'overview': (1920, 1080), 'approach': (1280, 720),
         'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}
REVIEWS = ('taxicab-review.json', 'sign-review.json',
           'passenger-purpose-review.json', 'ordinary-rules-review.json')
ROWS = ('yellow-zone-native.jsonl', 'observed-passenger-activity.jsonl',
        'video_frames.jsonl', 'trace.jsonl')
SOURCES = (*ROWS, 'road.xodr', 'yellow-road.xodr',
           'sign-authority-pending.json',
           *(view + '.mkv' for view in VIEWS), *REVIEWS)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def decode(path, dimensions):
    completed = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=nb_read_frames,width,height,r_frame_rate', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True, timeout=180)
    streams = json.loads(completed.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Exact one-camera video stream required: ' + path.name)
    stream = streams[0]
    if ((stream.get('width'), stream.get('height')) != dimensions or
            stream.get('r_frame_rate') != '20/1' or
            stream.get('nb_read_frames') != '600'):
        raise ValueError('Camera decode profile differs: ' + path.name)
    full = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
        '-map', '0:v:0', '-f', 'null', '-'], capture_output=True, check=True,
        timeout=180)
    if full.stderr:
        raise ValueError('Full video decode emitted errors: ' + path.name)
    return {'frames': 600, 'width': dimensions[0], 'height': dimensions[1],
            'sha256': sha(path)}


def audit(attempt):
    attempt = Path(attempt).resolve()
    source_path = attempt / 'source-manifest.json'
    seal_path = attempt / 'capture-seal.json'
    if not source_path.is_file() or not seal_path.is_file():
        raise ValueError('Original reviewed source manifest or capture seal missing')
    source = json.loads(source_path.read_text())
    seal = json.loads(seal_path.read_text())
    if (source.get('source_kind') != 'original_native' or
            source.get('capture_seal_sha256') != sha(seal_path) or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('frames') != 600):
        raise ValueError('Original source and Native seal binding differs')
    bound = source.get('sha256', {})
    if not isinstance(bound, dict) or set(bound) != set(SOURCES):
        raise ValueError('Exact independent original taxi source set required')
    for name in SOURCES:
        path = attempt / name
        if not path.is_file() or bound.get(name) != sha(path):
            raise ValueError('Original source changed or missing: ' + name)
        if name in seal.get('sources', {}) and seal['sources'][name] != bound[name]:
            raise ValueError('Capture seal source changed: ' + name)
    reviews = {name: json.loads((attempt / name).read_text()) for name in REVIEWS}
    for name, review in reviews.items():
        if (review.get('source_kind') != 'original_native' or
                not review.get('source_basis') or
                review.get('legal_verdict') is not None):
            raise ValueError('Independent original review missing: ' + name)
    if (reviews['taxicab-review.json'].get('observed_taxicab') is not True or
            reviews['sign-review.json'].get('observed_curb_color') != 'yellow' or
            not reviews['sign-review.json'].get('observed_sign_content') or
            reviews['passenger-purpose-review.json'].get('observed_purpose') not in
            ('waiting_for_passengers', 'loading_passengers', 'unloading_passengers')):
        raise ValueError('Original taxi identity, sign or passenger review differs')
    native, activity, mapping, trace = [read_rows(attempt / name) for name in ROWS]
    if any(len(rows) != 600 for rows in (native, activity, mapping, trace)):
        raise ValueError('Full 600-frame original source join required')
    taxi_actor = native[0].get('taxi_actor_id')
    passenger_actor = native[0].get('passenger_proxy_id')
    if (type(taxi_actor) is not int or type(passenger_actor) is not int or
            taxi_actor == passenger_actor):
        raise ValueError('Original taxi and passenger actor identities missing')
    for index, (n, a, m, t) in enumerate(zip(native, activity, mapping, trace)):
        frame, time_s = n.get('native_frame'), (index + 1) / 20
        if (n.get('source_kind') != 'original_native' or
                n.get('video_frame') != index or m.get('video_frame') != index or
                m.get('carla_frame') != frame or t.get('frame') != frame or
                not isinstance(frame, int) or
                any(not math.isclose(row.get('time_s', -1), time_s, abs_tol=1e-4)
                    for row in (n, m, t)) or
                m.get('camera_native_frames') != {view: frame for view in VIEWS} or
                n.get('source_cameras') != m.get('camera_native_frames') or
                n.get('taxi_actor_id') != taxi_actor or
                n.get('passenger_proxy_id') != passenger_actor or
                (index and frame <= native[index - 1].get('native_frame', -1))):
            raise ValueError('Original taxi camera and time join differs')
        if (a.get('source_kind') != 'original_native' or
                a.get('video_frame') != index or
                a.get('native_frame') != frame or
                not math.isclose(a.get('time_s', -1), time_s, abs_tol=1e-4) or
                type(a.get('observed_door_open')) is not bool or
                type(a.get('observed_occupant_count')) is not int or
                a['observed_occupant_count'] < 0 or
                a.get('observed_purpose') !=
                reviews['passenger-purpose-review.json']['observed_purpose']):
            raise ValueError('Original taxi passenger activity join differs')
    video = {view: decode(attempt / (view + '.mkv'), dims)
             for view, dims in VIEWS.items()}
    return {'format': 'c150173-independent-original-source-audit-v1',
            'frames': 600, 'source_manifest_sha256': sha(source_path),
            'capture_seal_sha256': sha(seal_path), 'videos': video,
            'original_native_source_join': True,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.attempt)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
