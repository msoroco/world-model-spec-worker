"""Check original-mode FFV1 full-decode guards with synthetic media only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c104496-full-decode'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make(path, frames):
    run = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                          '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:r=20',
                          '-frames:v', str(frames), '-c:v', 'ffv1', '-level', '1',
                          '-threads', '2', '-y', str(path)], capture_output=True,
                         text=True, timeout=300)
    if run.returncode:
        raise AssertionError(run.stderr)


def invoke(branch, path):
    code = ('import process_original,sys; '
            'print(process_original.ffv1_frames(__import__("pathlib").Path(sys.argv[1])))')
    return subprocess.run([sys.executable, '-c', code, str(path)],
                          cwd=HERE / 'native' / branch, capture_output=True,
                          text=True, timeout=300)


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    good = SCRATCH / 'west_view.mkv'
    short = SCRATCH / 'west_view_short.mkv'
    broken = SCRATCH / 'west_view_broken.mkv'
    make(good, 700)
    make(short, 699)
    broken.write_bytes(good.read_bytes()[:len(good.read_bytes()) // 2])
    rows = []
    for branch in ('crest', 'curve'):
        positive = invoke(branch, good)
        if positive.returncode or positive.stdout.strip() != sha(good):
            raise AssertionError(branch + ' full decode positive: ' + positive.stderr)
        negative_short = invoke(branch, short)
        negative_broken = invoke(branch, broken)
        if negative_short.returncode == 0 or negative_broken.returncode == 0:
            raise AssertionError(branch + ' accepted incomplete camera media')
        rows.append({'branch': branch, 'positive_exit_code': positive.returncode,
                     'short_negative_exit_code': negative_short.returncode,
                     'broken_negative_exit_code': negative_broken.returncode,
                     'processor_sha256': sha(HERE / 'native' / branch / 'process_original.py')})
    proof = {'format': 'c104496-full-camera-decode-diagnostic-v1',
             'synthetic_media_only': True, 'frames': 700, 'rate_hz': 20,
             'duration_s': 35, 'resolution': [1280, 720],
             'ffv1_sha256': sha(good), 'branches': rows,
             'original_native_observed': False, 'accepted': False}
    (HERE / 'native/full-camera-decode-proof.json').write_text(
        json.dumps(proof, sort_keys=True, indent=2) + '\n')
    print(json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    main()
