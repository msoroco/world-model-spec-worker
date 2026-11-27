"""CPU check of canonical four camera byte/frame joins and FFV1 decoding."""

import hashlib
import io
import json
import queue
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from runner import cameras, write_joined_camera_frame

SCRATCH = ROOT.parents[1] / '.runtime-work' / 'c228508-camera-proof'
SCRATCH.mkdir(parents=True, exist_ok=True)


class Image:
    def __init__(self, frame, raw_data):
        self.frame, self.raw_data = frame, raw_data


class Encoder:
    def __init__(self):
        self.stdin = io.BytesIO()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


profile = cameras()
assert [(p['width'], p['height']) for p in profile] == [
    (1920, 1080), (1280, 720), (1280, 720), (1280, 720)]
assert len({p['name'] for p in profile}) == 4
proofs = []
for index, spec in enumerate(profile):
    shape = (spec['height'], spec['width'], 4)
    pixels = np.zeros(shape, dtype=np.uint8)
    pixels[:, :, 0] = 20 + index
    pixels[:, :, 1] = 40 + index
    pixels[:, :, 2] = 60 + index
    pixels[:, :, 3] = 255
    source = queue.Queue()
    source.put(Image(40, pixels.tobytes()))
    source.put(Image(41, pixels.tobytes()))
    encoder = Encoder()
    joined = write_joined_camera_frame(41, spec, source, encoder, np)
    assert joined['native_frame'] == joined['camera_frame'] == 41
    assert len(encoder.stdin.getvalue()) == spec['width'] * spec['height'] * 3
    path = SCRATCH / (spec['name'] + '.mkv')
    cmd = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s',
           f"{spec['width']}x{spec['height']}", '-r', '20', '-i', 'pipe:0',
           '-an', '-c:v', 'ffv1', '-level', '1', str(path)]
    encoded = subprocess.run(cmd, input=encoder.stdin.getvalue(), capture_output=True)
    if encoded.returncode:
        raise RuntimeError(encoded.stderr.decode()[-1000:])
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-show_entries', 'stream=width,height,codec_name,nb_frames',
                            '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    stream = json.loads(probe.stdout)['streams'][0]
    assert stream['width'] == spec['width'] and stream['height'] == spec['height']
    assert stream['codec_name'] == 'ffv1'
    decoded = subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                              '-f', 'null', '-'], capture_output=True, text=True)
    assert decoded.returncode == 0, decoded.stderr
    proofs.append({'view': spec['name'], 'width': spec['width'], 'height': spec['height'],
                   'joined_frame': 41, 'encoded_input_bytes': joined['encoded_input_bytes'],
                   'ffv1_sha256': digest(path), 'full_decode_exit_code': 0})

negative = {}
spec = {'name': 'tiny', 'width': 2, 'height': 2}
for name, images, expected in [
    ('future_frame', [Image(42, bytes(16))], 'camera/Native frame join'),
    ('missing_source_pixels', [Image(41, bytes(12))], 'source byte count')]:
    source = queue.Queue()
    for image in images:
        source.put(image)
    try:
        write_joined_camera_frame(41, spec, source, Encoder(), np)
    except (ValueError, RuntimeError) as error:
        assert expected in str(error)
        negative[name] = str(error)
    else:
        raise AssertionError('Damaged camera source was accepted: ' + name)

result = {'format': 'c228508-four-view-source-camera-cpu-proof-v1',
          'runner_sha256': digest(ROOT / 'native' / 'runner.py'),
          'views': proofs, 'negative_rejections': negative,
          'synthetic_pixels_only': True, 'native_camera_visibility_claimed': False,
          'selected_delivery_claimed': False}
output = ROOT / 'camera-proof.json'
output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'proof_sha256': digest(output), 'decoded_views': len(proofs),
                  'negative_rejections': len(negative)}))
