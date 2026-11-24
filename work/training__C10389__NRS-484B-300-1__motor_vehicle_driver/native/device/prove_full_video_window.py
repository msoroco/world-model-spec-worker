"""Decode every frame of a synthetic 30-second four-source device capture."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from verify_media import verify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VIEWS = (('overview', '1920x1080', 'blue'),
         ('approach', '1280x720', 'red'),
         ('reference_corner', '1280x720', 'green'),
         ('driver_reference', '1280x720', 'yellow'))
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run(args, capture_output=True, text=True, timeout=900)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('FFV1 generation failed: ' + result.stderr[-2000:])


def prove():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    scratch = ROOT / '.runtime-work' / ('c10389-full-video-' + uuid.uuid4().hex[:12])
    scratch.mkdir(parents=True)
    logs = {}
    for name, size, color in VIEWS:
        log = scratch / (name + '-encode.log')
        command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                 '-f', 'lavfi', '-i', f'color=c={color}:s={size}:r=20',
                 '-frames:v', str(FRAMES), '-c:v', 'ffv1',
                 str(scratch / (name + '.mkv'))], log)
        logs[name] = sha(log)
    compose_log = scratch / 'compose.log'
    command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
             *sum((['-i', str(scratch / (name + '.mkv'))] for name, _, _ in VIEWS), []),
             '-filter_complex',
             'xstack=inputs=4:layout=960_0|0_1080|1280_1080|2560_1080:fill=black',
             '-an', '-c:v', 'ffv1', str(scratch / 'raw.mkv')], compose_log)
    media_hashes = verify(scratch, FRAMES)
    truncated = scratch / 'truncated'
    truncated.mkdir()
    for name, _, _ in VIEWS:
        if name != 'approach':
            shutil.copyfile(scratch / (name + '.mkv'), truncated / (name + '.mkv'))
    command(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
             '-f', 'lavfi', '-i', 'color=c=red:s=1280x720:r=20',
             '-frames:v', '599', '-c:v', 'ffv1', str(truncated / 'approach.mkv')],
            scratch / 'truncated-encode.log')
    shutil.copyfile(scratch / 'raw.mkv', truncated / 'raw.mkv')
    try:
        verify(truncated, FRAMES)
    except ValueError as error:
        assert 'camera profile or frame count: approach.mkv' in str(error)
    else:
        raise AssertionError('Truncated source camera accepted')
    receipt = {'format': 'c10389-full-video-window-cpu-v1',
               'source_kind': 'synthetic_cpu', 'frames': FRAMES, 'rate_hz': 20,
               'duration_s': 30, 'media_sha256': media_hashes,
               'encode_log_sha256': logs, 'compose_log_sha256': sha(compose_log),
               'truncated_source_rejected': True, 'full_decode_passed': True,
               'verify_media_sha256': sha(HERE / 'verify_media.py'),
               'capture_sha256': sha(HERE / 'capture.py'),
               'physical_observation_claimed': False, 'selected_delivery_claimed': False}
    target = HERE / 'offline' / 'full-video-window-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'frames': FRAMES, 'videos_decoded': len(media_hashes),
                      'truncated_source_rejected': True, 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    prove()
