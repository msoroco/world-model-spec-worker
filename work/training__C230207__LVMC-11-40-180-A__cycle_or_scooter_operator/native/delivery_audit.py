"""Independent source and pixel audit; actual physical claims require original review."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from measure import measure

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
AID = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('bicycle-poses.jsonl', 'restriction-context.json', 'video_frames.jsonl',
           'road.xodr', 'trace.jsonl')


def require(value, message):
    if not value:
        raise ValueError(message)


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(root in path.parents and path.is_file(), 'Missing delivery source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, size):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                            '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate',
                            '-of', 'json', str(path)], capture_output=True, text=True, timeout=180)
    require(probe.returncode == 0, 'Full video decode failed')
    streams = json.loads(probe.stdout).get('streams', [])
    require(len(streams) == 1, 'Full video source inventory differs')
    stream = streams[0]
    require(stream.get('nb_read_frames') == '600' and stream.get('r_frame_rate') == '20/1',
            'Full video frame count or rate differs')
    require((stream.get('width'), stream.get('height')) == size,
            'Full video dimensions differ')
    pixels = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                             '-i', str(path), '-frames:v', '1', '-f', 'rawvideo',
                             '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=180)
    require(pixels.returncode == 0 and len(pixels.stdout) == size[0] * size[1] * 3,
            'Actual decoded pixels absent')
    return {'frames': 600, 'rate_hz': 20, 'width': size[0], 'height': size[1],
            'sha256': sha(path), 'first_frame_rgb_sha256': hashlib.sha256(pixels.stdout).hexdigest()}


def audit(root, case, diagnostic=False):
    require(case in (AID + '__controlled_1', AID + '__controlled_2'),
            'Wrong Fremont sidewalk delivery case')
    root = Path(root).resolve()
    paths = {name: source(root, name) for name in SOURCES}
    context = json.loads(paths['restriction-context.json'].read_text())
    behavior = 'walk_cycle' if case.endswith('_1') else 'mounted_sidewalk'
    require(context.get('controlled_behavior') == behavior,
            'Original controlled behavior differs')
    observed = measure(paths['bicycle-poses.jsonl'], paths['restriction-context.json'],
                       paths['video_frames.jsonl'])
    trace = [json.loads(line) for line in paths['trace.jsonl'].read_text().splitlines()]
    poses = [json.loads(line) for line in paths['bicycle-poses.jsonl'].read_text().splitlines()]
    require(len(trace) == len(poses) == 600 and all(
        trace[i].get('frame') == poses[i].get('native_frame') and
        abs(trace[i].get('time_s', -1) - poses[i]['time_s']) < 1e-6
        for i in range(600)), 'Original cycle trace join failed')
    require(observed['sidewalk_occupied_frames'] > 0,
            'Original sidewalk occupancy source absent')
    if diagnostic:
        video = decode(source(root, 'diagnostic.mkv'), (64, 36))
        return {'format': 'worker-c230207-source-audit-v1', 'case_id': case,
                'diagnostic_fixture': True, 'native_executed': False,
                'source_join_frames': 600, 'synthetic_pixel_decode': video,
                'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    videos = {name: decode(source(root, name + '.mkv'),
                           (1920, 1080) if name == 'overview' else (1280, 720))
              for name in VIEWS}
    review_path = source(root, 'fremont-original-review.json')
    review = json.loads(review_path.read_text())
    require(review.get('original_pixel_reviewed') is True and
            review.get('named_geography_verified') is True and
            review.get('sign_face_three_class_text_verified') is True and
            review.get('bicycle_class_independently_verified') is True and
            review.get('sidewalk_occupancy_reviewed') is True and
            review.get('operator_posture_reviewed') is True,
            'Original sidewalk, sign, device or posture review missing')
    require(review.get('observed_behavior') == behavior,
            'Original operator behavior differs from selected case')
    require(review.get('video_sha256') == {name + '.mkv': videos[name]['sha256'] for name in VIEWS}
            and review.get('source_sha256') == {name: sha(path) for name, path in paths.items()},
            'Original source review hash differs')
    result = json.loads(source(root, 'result.json').read_text())
    require(result.get('case_id') == case and result.get('maneuver_completed') is True,
            'Original Native physical completion unverified')
    seal = json.loads(source(root, 'capture-seal.json').read_text())
    require(seal.get('provenance_kind') == 'native' and seal.get('diagnostic_fixture') is False,
            'Sealed original Native source missing')
    return {'format': 'worker-c230207-source-audit-v1', 'case_id': case,
            'passed': True, 'native_executed': True,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_sha256': {name: sha(path) for name, path in paths.items()},
            'video_decode': videos, 'review_sha256': sha(review_path),
            'legal_verdict_claimed': False}


def selftest(case, negative=False):
    require(case in (AID + '__controlled_1', AID + '__controlled_2'),
            'Wrong selftest case')
    stem = 'walk_cycle' if case.endswith('_1') else 'mounted_sidewalk'
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c230207-delivery-audit-') as directory:
        root = Path(directory)
        for name in SOURCES:
            shutil.copyfile(HERE / 'diagnostic-source' / stem / name, root / name)
        if negative:
            (root / 'restriction-context.json').unlink()
        else:
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=black:s=64x36:r=20',
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            str(root / 'diagnostic.mkv')], check=True, timeout=180)
        return audit(root, case, diagnostic=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    result = selftest(args.case, args.negative_selftest) if (
        args.selftest or args.negative_selftest) else audit(args.attempt, args.case)
    print(json.dumps(result, sort_keys=True))
