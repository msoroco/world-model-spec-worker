"""Independent original bus, wheel, traffic, timing and pixel audit."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
AID = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = {name: ((1920, 1080) if name == 'overview' else (1280, 720))
         for name in VIEWS}
SOURCES = ('video_frames.jsonl', 'bus-traffic-poses.jsonl', 'bus-zone-review.json',
           'trace.jsonl', 'road.xodr', 'curb-calibration.json',
           'bus-classification.json', 'wheel-geometry.json', 'loading-location.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(root in path.parents and path.is_file(), 'Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path, size=None):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=nb_read_frames,width,height,r_frame_rate', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=180)
    require(run.returncode == 0, 'Full bus video decode failed')
    streams = json.loads(run.stdout).get('streams', [])
    require(len(streams) == 1, 'Full bus video stream inventory differs')
    meta = streams[0]
    require(meta.get('nb_read_frames') == '600' and
            meta.get('r_frame_rate') == '20/1',
            'Full bus video frame count or rate differs')
    if size:
        require((int(meta['width']), int(meta['height'])) == size,
                'Full bus video dimensions differ')
    pixel = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel',
        'error', '-i', str(path), '-frames:v', '1', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=180)
    require(pixel.returncode == 0 and len(pixel.stdout) ==
            int(meta['width']) * int(meta['height']) * 3,
            'Actual decoded bus pixels absent')
    return {'frames': 600, 'rate_hz': 20, 'width': int(meta['width']),
            'height': int(meta['height']), 'sha256': sha(path),
            'first_frame_rgb_sha256': hashlib.sha256(pixel.stdout).hexdigest()}


def audit(root, case, diagnostic=False):
    suffix = case.rsplit('__', 1)[-1]
    require(case == AID + '__' + suffix and suffix in ('probe_1', 'probe_2', 'probe_3'),
            'Wrong exact bus delivery case')
    paths = {name: source(root, name) for name in SOURCES}
    frames, poses, trace = (rows(paths[name]) for name in
                            ('video_frames.jsonl', 'bus-traffic-poses.jsonl',
                             'trace.jsonl'))
    review = json.loads(paths['bus-zone-review.json'].read_text())
    require(review.get('assignment_id') == AID and
            review.get('case_id') == case and
            review.get('vehicle_class') == 'non_tour_bus' and
            review.get('location_kind') in ('bus_stop', 'bus_stand',
                'passenger_loading_zone', 'origin', 'destination') and
            review.get('public_street') is True,
            'Selected bus loading scope differs')
    require(review.get('review_kind') == ('synthetic_diagnostic' if diagnostic
            else 'original_source_review'), 'Independent bus source review absent')
    for key, name in {'native_map_sha256': 'road.xodr',
            'curb_calibration_sha256': 'curb-calibration.json',
            'bus_classification_sha256': 'bus-classification.json',
            'wheel_geometry_sha256': 'wheel-geometry.json',
            'loading_zone_sha256': 'loading-location.json'}.items():
        require(review.get(key) == sha(paths[name]),
                'Reviewed bus source hash differs: ' + name)
    require(len(frames) == len(poses) == len(trace) == 600,
            'Full Native bus/traffic trace join missing')
    bus_ids = {r.get('bus_id') for r in poses}
    traffic_ids = {r.get('other_vehicle_id') for r in poses}
    require(len(bus_ids) == len(traffic_ids) == 1 and bus_ids != traffic_ids,
            'Distinct bus and other-vehicle identities missing')
    for i, (frame, pose, state) in enumerate(zip(frames, poses, trace)):
        require(frame.get('video_frame') == pose.get('video_frame') == i and
                frame.get('native_frame') == pose.get('native_frame') ==
                    state.get('frame') and
                abs(frame['time_s'] - pose['time_s']) < 1e-4 and
                abs(frame['time_s'] - state['time_s']) < 1e-4 and
                abs(pose['bus_observed_speed_mps'] - state['speed_mps']) < 1e-3 and
                all(abs(a - b) < 1e-3 for a, b in
                    zip(pose['bus_xyz_m'][:2], state['position_m'][:2])),
                'Native bus/traffic frame or pose differs')
        require(set(pose.get('camera_native_frames', {})) == set(VIEWS) and
                all(pose['camera_native_frames'][name] == frame['native_frame']
                    for name in VIEWS), 'Original source camera frame differs')
    require(frames[-1]['time_s'] - frames[0]['time_s'] >= 29.9,
            'Full 30-second bus source period missing')
    if diagnostic:
        video = decode(source(root, 'diagnostic.mkv'))
        proof = json.loads((HERE / 'physical-proof' / suffix /
                            'complete_motion.json').read_text())
        require(proof['physical_checks']['maneuver']['status'] == 'met' and
                proof['diagnostic_fixture'] is True,
                'Diagnostic bus physical fixture not met')
        return {'format': 'worker-lvmc-bus-source-audit-v1', 'case_id': case,
            'diagnostic_fixture': True, 'native_executed': False,
            'source_join_frames': 600, 'synthetic_pixel_decode': video,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}
    videos = {name: decode(source(root, name + '.mkv'), SIZES[name])
              for name in VIEWS}
    review_path = source(root, 'bus-original-review.json')
    original = json.loads(review_path.read_text())
    require(all(original.get(key) is True for key in
        ('original_pixel_reviewed', 'bus_non_tour_classification_reviewed',
         'public_street_and_location_reviewed', 'loading_activity_reviewed',
         'curb_wheel_geometry_reviewed', 'other_traffic_reviewed')),
        'Original bus loading and traffic review missing')
    require(original.get('camera_sha256') ==
            {v + '.mkv': videos[v]['sha256'] for v in VIEWS} and
            original.get('source_sha256') ==
            {name: sha(path) for name, path in paths.items()},
            'Original bus source review hash differs')
    result = json.loads(source(root, 'result.json').read_text())
    require(result.get('case_id') == case and
            result.get('maneuver_completed') is True and
            result.get('physical_checks', {}).get('maneuver', {}).get('status') == 'met',
            'Original Native bus physical completion unverified')
    return {'format': 'worker-lvmc-bus-source-audit-v1', 'case_id': case,
        'passed': True, 'native_executed': True,
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'source_sha256': {name: sha(path) for name, path in paths.items()},
        'video_decode': videos, 'review_sha256': sha(review_path),
        'legal_verdict_claimed': False}


def selftest(case, negative):
    suffix = case.rsplit('__', 1)[-1]
    require(case == AID + '__' + suffix, 'Wrong bus selftest case')
    diagnostic = json.loads((HERE / 'cases' / suffix / 'diagnostic.json').read_text())
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c149507-source-audit-') as temp:
        stage = Path(temp)
        for name in SOURCES:
            (stage / name).write_text(diagnostic['files'][name])
        if negative:
            (stage / 'bus-traffic-poses.jsonl').unlink()
        else:
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel',
                'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x36:r=20',
                '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                str(stage / 'diagnostic.mkv')], check=True, timeout=180)
        return audit(stage, case, diagnostic=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    result = (selftest(args.case, args.negative_selftest)
              if args.selftest or args.negative_selftest else
              audit(args.attempt, args.case))
    print(json.dumps(result, sort_keys=True))
