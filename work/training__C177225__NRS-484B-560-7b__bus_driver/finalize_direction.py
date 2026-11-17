"""Source-reading saved observation for the directed rail officer comparison."""
import hashlib
import json
from pathlib import Path
import subprocess

from measure_direction import derive_observation
from native_scene import VIEWS
from officer_direction import Crossing, OfficerStop


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing saved source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _media(path, expected_frames, size):
    if not path.is_file():
        raise ValueError('Missing saved source camera: ' + path.name)
    result = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames,width,height,r_frame_rate,codec_name',
        '-of', 'json', str(path)], capture_output=True, text=True,
        check=True, timeout=120)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('Source camera has no unique video stream: ' + path.name)
    stream = streams[0]
    if (int(stream['nb_read_frames']) != expected_frames or
            (stream['width'], stream['height']) != tuple(size) or
            stream['r_frame_rate'] != '20/1' or
            stream['codec_name'] != 'ffv1'):
        raise ValueError('Saved source camera profile/frame mismatch: ' + path.name)
    return {'path': path.name, 'sha256': _sha(path),
            'decoded_frames': expected_frames, 'width': size[0], 'height': size[1]}


def process_saved(root, *, source_kind='original_native'):
    root = Path(root)
    config_path = root / 'config.json'
    signal_path = root / 'officer_signal_definition.json'
    if not config_path.is_file() or not signal_path.is_file():
        raise ValueError('Missing saved exact-case configuration or signal')
    config = json.loads(config_path.read_text())
    signal = OfficerStop(**json.loads(signal_path.read_text()))
    if config.get('case_suffix') not in ('reference', 'contrast') or (
            config.get('case_id') != signal_case_id(config['case_suffix']) or
            config.get('direction') != signal.direction or
            config.get('rate_hz') != 20 or
            type(config.get('frames')) is not int or config['frames'] < 2):
        raise ValueError('Saved exact case/capture profile differs')
    if source_kind == 'original_native':
        manifest = root / 'capture' / 'manifest.json'
        if not manifest.is_file() or not json.loads(manifest.read_text()).get('extraction_confirmed'):
            raise ValueError('Missing confirmed original PipelineCapture source')
    bus_path = root / 'bus_native_rows.jsonl'
    officer_path = root / 'officer_signal_rows.jsonl'
    frame_path = root / 'video_frames.jsonl'
    bus = _rows(bus_path)
    officer = _rows(officer_path)
    mapping = _rows(frame_path)
    if not len(bus) == len(officer) == len(mapping) == config['frames']:
        raise ValueError('Saved Native row count differs from exact capture profile')
    specs = {name: size for name, size in (
        ('overview', (1280, 720)), ('approach', (1280, 720)),
        ('reference_corner', (1280, 720)), ('driver_reference', (1280, 720)))}
    if set(specs) != set(VIEWS):
        raise ValueError('Four source camera names differ')
    media = {name: _media(root / (name + '.mkv'), len(mapping), specs[name])
             for name in VIEWS}
    observation = derive_observation(Crossing(), signal, bus, officer, mapping,
                                     source_kind=source_kind)
    observation['saved_source_sha256'] = {
        path.name: _sha(path)
        for path in (config_path, signal_path, bus_path, officer_path, frame_path)}
    observation['saved_camera_sources'] = media
    observation['physical_visibility_reviewed'] = False
    observation['legal_verdict'] = None
    return observation


def signal_case_id(suffix):
    return 'training__C177225__NRS-484B-560-7b__bus_driver__' + suffix
