"""Exercise the current four-view FFV1 composition with synthetic pixels."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import shutil
from verify_media import verify

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
VIEWS = (('overview', '1920x1080', 'blue'),
         ('approach', '1280x720', 'red'),
         ('reference_corner', '1280x720', 'green'),
         ('driver_reference', '1280x720', 'yellow'))


def run(args):
    subprocess.run(args, check=True, capture_output=True, text=True, timeout=180)


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=codec_name,nb_read_frames,width,height,r_frame_rate',
        '-of', 'json', str(path)], check=True, capture_output=True, text=True,
        timeout=120)
    return json.loads(result.stdout)['streams'][0]


def prove():
    output = ROOT / '.runtime-work' / ('c10389-video-' + uuid.uuid4().hex[:12])
    output.mkdir(parents=True)
    for name, size, color in VIEWS:
        run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
            '-f', 'lavfi', '-i', f'color=c={color}:s={size}:r=20',
            '-frames:v', '2', '-c:v', 'ffv1', str(output / (name + '.mkv'))])
    run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
        *sum((['-i', str(output / (name + '.mkv'))] for name, _, _ in VIEWS), []),
        '-filter_complex',
        'xstack=inputs=4:layout=960_0|0_1080|1280_1080|2560_1080:fill=black',
        '-an', '-c:v', 'ffv1', str(output / 'raw.mkv')])
    expected = {name + '.mkv': tuple(map(int, size.split('x')))
                for name, size, _ in VIEWS}
    expected['raw.mkv'] = (3840, 1800)
    for name, dimensions in expected.items():
        row = probe(output / name)
        if (row.get('codec_name') != 'ffv1' or
                row.get('nb_read_frames') != '2' or
                row.get('r_frame_rate') != '20/1' or
                (row.get('width'), row.get('height')) != dimensions):
            raise ValueError('four-view synthetic video profile: ' + name)
    media_hashes = verify(output, 2)
    missing = output / 'missing-source'
    missing.mkdir()
    for name in expected:
        if name != 'driver_reference.mkv':
            shutil.copyfile(output / name, missing / name)
    try:
        verify(missing, 2)
    except FileNotFoundError:
        missing_rejected = True
    else:
        raise ValueError('missing source camera accepted')
    damaged = output / 'damaged-source'
    damaged.mkdir()
    for name in expected:
        shutil.copyfile(output / name, damaged / name)
    (damaged / 'approach.mkv').write_bytes(b'not-an-FFV1-stream')
    try:
        verify(damaged, 2)
    except (ValueError, subprocess.CalledProcessError):
        damaged_rejected = True
    else:
        raise ValueError('damaged source camera accepted')
    receipt = {'format': 'c10389-synthetic-four-view-proof-v2',
        'source_kind': 'synthetic_cpu', 'source_views': list(expected)[:-1],
        'composed_view': 'raw.mkv', 'frame_count': 2, 'fps': 20,
        'composed_dimensions': [3840, 1800], 'full_decode_passed': True,
        'all_five_media_hashes': media_hashes,
        'missing_source_rejected': missing_rejected,
        'damaged_source_rejected': damaged_rejected,
        'capture_sha256': hashlib.sha256((HERE / 'capture.py').read_bytes()).hexdigest(),
        'saved_sha256': hashlib.sha256((HERE / 'saved.py').read_bytes()).hexdigest(),
        'original_native_observed': False, 'delivery_ready': False}
    target = HERE / 'offline' / 'video-profile-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(prove()))
