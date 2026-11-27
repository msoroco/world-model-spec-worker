"""Independent CPU audit of source joins, video pixels, and synthetic completion."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from signed_access_measure import CAMERAS, derive

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name
TARGETS = {'witness_1': 0, 'witness_2': 400}
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def video(path):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=nb_read_frames,width,height,r_frame_rate', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=120, check=True)
    row = json.loads(probe.stdout)['streams'][0]
    require(row['nb_read_frames'] == '9' and row['r_frame_rate'] == '20/1',
            'Full video decode count differs')
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel',
        'error', '-i', str(path), '-frames:v', '1', '-f', 'rawvideo',
        '-pix_fmt', 'rgb24', '-'], capture_output=True, timeout=120, check=True)
    require(len(decoded.stdout) == int(row['width']) * int(row['height']) * 3,
            'Actual decoded pixels missing')
    return {'frames': 9, 'sha256': sha(path),
            'first_pixel_sha256': hashlib.sha256(decoded.stdout).hexdigest()}


def audit(case, attempt, negative=False):
    suffix = case.rsplit('__', 1)[-1]
    require(case == AID + '__' + suffix and suffix in TARGETS,
            'Wrong selected signed-road case')
    attempt = Path(attempt).resolve()
    require((REPO / '.runtime-work').resolve() in attempt.parents,
            'Diagnostic attempt must be scratch')
    if negative:
        with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                         prefix='c230207-delivery-negative-') as tmp:
            root = Path(tmp)
            shutil.copy2(attempt / 'raw-frames.json', root / 'raw-frames.json')
            derive(root)
        raise ValueError('Negative missing-source audit unexpectedly passed')
    measured = derive(attempt)
    require(measured['source_kind'] == 'synthetic_native_sample' and
            measured['diagnostic_excerpt'] is True and
            measured['riding_frames'] == 9 and
            measured['inside_governed_segment_frames'] ==
            (0 if suffix == 'witness_1' else 9),
            'Source-bound diagnostic riding comparison differs')
    frames = json.loads((attempt / 'raw-frames.json').read_text())
    mapped = [json.loads(line) for line in
              (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(len(frames) == len(mapped) == 9 and all(
        row['frame'] == i and mapped[i]['native_frame'] == row['native_frame']
        and abs(mapped[i]['time_s'] - row['elapsed_s'] - 0.05) < 1e-6
        for i, row in enumerate(frames)), 'Frame/time join differs')
    videos = {view: video(attempt / (view + '.mkv')) for view in CAMERAS}
    physical = json.loads((HERE / 'physical' / suffix /
                           'complete_motion-result.json').read_text())
    require(physical['physical_checks']['maneuver']['status'] == 'met' and
            physical['realized_observables']['signed_roadway_riding_frames'] ==
            TARGETS[suffix] and physical['diagnostic_fixture'] is True,
            '600-frame synthetic physical completion differs')
    return {'format': 'c230207-delivery-audit-v1', 'case_id': case,
            'checks': CHECKS, 'diagnostic_excerpt_frames': 9,
            'full_length_synthetic_frames': 600, 'videos': videos,
            'original_native_executed': False,
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.negative_selftest),
                     sort_keys=True))
