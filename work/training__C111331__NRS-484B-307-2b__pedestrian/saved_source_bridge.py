"""Join retained Native-shaped sources without promoting requested signal state."""
import hashlib
import json
from pathlib import Path
import subprocess

from saved_entry_measurement import measure

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _decoded(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        text=True, capture_output=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source camera decode failed: ' + path.name)
    return int(result.stdout.strip())


def join(root, crosswalk, governance):
    root = Path(root)
    native = _rows(root / 'c111331-native-samples.jsonl')
    mapping = _rows(root / 'video_frames.jsonl')
    if len(native) != 600 or len(mapping) != 600:
        raise ValueError('600 original Native and camera-map rows required')
    videos = {name: root / (name + '.mkv') for name in VIEWS}
    for name, path in videos.items():
        if _decoded(path) != 600:
            raise ValueError('600 decoded source frames required: ' + name)
    frames = []
    for index, (sample, frame) in enumerate(zip(native, mapping)):
        if sample.get('video_frame') != index or frame.get('video_frame') != index:
            raise ValueError('Source video frame identity differs')
        if sample.get('native_frame') != frame.get('native_frame'):
            raise ValueError('Native and camera frame identities differ')
        if abs(sample.get('time_s', -1) - frame.get('time_s', -2)) > 1e-6:
            raise ValueError('Native and camera timestamps differ')
        hashes = frame.get('source_rgb_sha256')
        if not isinstance(hashes, dict) or set(hashes) != set(VIEWS) or any(
                not isinstance(v, str) or len(v) != 64 for v in hashes.values()):
            raise ValueError('Four source RGB hashes missing')
        traffic = sample.get('observed_traffic_signal')
        pedestrian = sample.get('observed_pedestrian_signal')
        if not isinstance(traffic, dict) or not isinstance(pedestrian, dict):
            raise ValueError('Observed traffic and pedestrian indications required; requests are insufficient')
        if traffic.get('source') != 'native_readback' or pedestrian.get('source') != 'native_readback':
            raise ValueError('Signal indication lacks observed Native provenance')
        frames.append({'frame': index, 'time_s': index / 20,
                       'pedestrian_id': sample.get('pedestrian_id'),
                       'pedestrian_xy': sample.get('pedestrian_xy_m'),
                       'traffic_signal': {'id': traffic.get('id'), 'state': traffic.get('state')},
                       'pedestrian_signal': {'id': pedestrian.get('id'), 'state': pedestrian.get('state')}})
    source = {'format': 'pedestrian-entry-raw-v1', 'hz': 20, 'frame_count': 600,
              'camera_ids': list(VIEWS), 'pedestrian_id': native[0].get('pedestrian_id'),
              'crosswalk': crosswalk, 'governing_devices': governance, 'frames': frames}
    measured = measure(source)
    return {'format': 'c111331-saved-source-bridge-v1', 'measurement': measured,
            'native_samples_sha256': hashlib.sha256((root / 'c111331-native-samples.jsonl').read_bytes()).hexdigest(),
            'video_map_sha256': hashlib.sha256((root / 'video_frames.jsonl').read_bytes()).hexdigest(),
            'source_video_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest()
                                    for name, path in videos.items()},
            'decoded_frames': 600, 'source_camera_names': list(VIEWS),
            'actual_signal_pixels_reviewed': False, 'governing_direction_physically_verified': False,
            'legal_verdict': None}
