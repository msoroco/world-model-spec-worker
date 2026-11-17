"""Source-reading saved observation for the directed rail officer comparison."""
import argparse
import hashlib
import json
import math
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
    for name in ('config.json', 'officer_signal_definition.json'):
        _required(root, name)
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


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def _joined_sources(root, mapping, bus, officer):
    trace = _rows(_required(root, 'trace.jsonl'))
    evidence = _rows(_required(root, 'capture/evidence.jsonl'))
    if len(trace) != len(mapping) or len(evidence) != len(mapping):
        raise ValueError('Saved trace/capture frame counts differ')
    for index, (mapped, point, packet, bus_row, signal_row) in enumerate(
            zip(mapping, trace, evidence, bus, officer)):
        frame = mapped.get('native_frame')
        time = mapped.get('time_s')
        if (mapped.get('video_frame') != index or type(frame) is not int or
                type(time) not in (int, float) or not math.isfinite(time) or
                point.get('frame') != frame or
                packet.get('original_frame') != frame or
                bus_row.get('native_frame') != frame or
                signal_row.get('native_frame') != frame or
                abs(point.get('time_s', -1) - time) > 1e-6 or
                abs(packet.get('recording_time_s', -1) - time) > 1e-6):
            raise ValueError('Saved trace/capture/actor frame join differs')
    return trace, evidence


def _derived_channels(root, description, bus, officer, mapping):
    expected = {'kin.velocity', 'drv.stopped', 'dev.human_direction',
                'native_actor_state', 'camera_frame_join'}
    channels = description.get('channels')
    if not isinstance(channels, list) or {c.get('name') for c in channels} != expected:
        raise ValueError('Exact recording channels differ')
    folder = root / 'channels'
    folder.mkdir(exist_ok=True)
    evidence = []
    for channel in channels:
        name = channel['name']
        relative = 'channels/' + name + '.jsonl'
        path = root / relative
        if path.exists():
            raise ValueError('Retain prior derived channel: ' + relative)
        with path.open('x') as stream:
            for b, s, m in zip(bus, officer, mapping):
                speed = sum(v * v for v in b['velocity_native_xyz_mps']) ** .5
                value = {'kin.velocity': speed, 'drv.stopped': speed <= .05,
                         'dev.human_direction': s, 'native_actor_state': b,
                         'camera_frame_join': m}[name]
                stream.write(json.dumps({'time_s': m['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': relative})
    return evidence


def measure_directed_officer_stop(root, observation):
    return {'value': {
                'stop_before_line': observation['observed_complete_stop_before_line'],
                'crossing_entry': observation['observed_crossing_entry'],
                'governing_frames': len(observation['officer_direction_witnessed_frames'])},
            'method': 'measure_directed_officer_stop',
            'sources': {name: _sha(_required(root, name)) for name in
                        ('bus_native_rows.jsonl', 'officer_signal_rows.jsonl',
                         'video_frames.jsonl')}}


def measure_vehicle_scope(root, config, bus):
    return {'value': {'actor': config['actor'],
                      'bus_actor_ids': sorted({row['actor_id'] for row in bus}),
                      'bus_blueprint_requested': 'vehicle.mitsubishi.fusorosa'},
            'method': 'measure_vehicle_scope',
            'sources': {name: _sha(_required(root, name)) for name in
                        ('config.json', 'bus_native_rows.jsonl')}}


def measure_authorized_direction(root, signal, officer):
    return {'value': {'authorized_role_authored': signal.authorized,
                      'verified_police_credential': False,
                      'officer_actor_id': signal.officer_id,
                      'recipient_bus_actor_id': signal.bus_id,
                      'crossing_id': signal.crossing_id,
                      'observed_pose_rows': len(officer)},
            'method': 'measure_authorized_direction',
            'sources': {name: _sha(_required(root, name)) for name in
                        ('officer_signal_definition.json', 'officer_signal_rows.jsonl')}}


def finalize_attempt(root, output):
    """Finalize saved acquisition only; never infer legal or physical acceptance."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config = json.loads(_required(root, 'config.json').read_text())
    observation = process_saved(root, source_kind='original_native')
    mapping = _rows(_required(root, 'video_frames.jsonl'))
    bus = _rows(_required(root, 'bus_native_rows.jsonl'))
    officer = _rows(_required(root, 'officer_signal_rows.jsonl'))
    signal = OfficerStop(**json.loads(_required(root, 'officer_signal_definition.json').read_text()))
    trace, _ = _joined_sources(root, mapping, bus, officer)
    description = config['recording_description']
    channel_evidence = _derived_channels(root, description, bus, officer, mapping)
    measured = observation['observed_complete_stop_before_line']
    requested = config['case_suffix'] == 'reference'
    target = {'target': 'bus_obeys_officer_direction', 'requested': requested,
              'measured': measured,
              'method': 'saved original bus velocity/station and directed officer frame join',
              'tolerance': 0, 'matched': measured == requested,
              'physical_cause_confirmed': False,
              'cause_evidence': ['bus_native_rows.jsonl',
                                 'officer_signal_rows.jsonl', 'video_frames.jsonl']}
    result = {'case_id': config['case_id'],
              'measured_values': {'officer_direction': {
                  key: value for key, value in observation.items()
                  if key != 'legal_verdict'}},
              'target_checks': [target], 'setup_confirmed': True,
              'behavior_attempted': bool(observation['officer_direction_witnessed_frames']),
              'maneuver_completed': observation['observed_crossing_entry'],
              'termination_reason': 'full saved capture duration retained',
              'physical_failure_flags': ['railway_identity_and_signal_visibility_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': channel_evidence,
              'realized_observables': {
                  'minimum_recorded_speed_mps': {
                      'value': observation['minimum_recorded_speed_mps'],
                      'unit': 'm/s', 'method': 'raw Native velocity vector norm',
                      'time_window': 'full saved capture', 'statistic': 'minimum',
                      'reference': 'bus_native_rows.jsonl'}},
              'provenance_kind': 'native', 'accepted': False,
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c177225-saved-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {
                  'vehicle_scope': measure_vehicle_scope(root, config, bus),
                  'directed_officer_stop': measure_directed_officer_stop(root, observation),
                  'authorized_direction': measure_authorized_direction(root, signal, officer)},
              'trace_frames': len(trace), 'scope': 'saved Native source diagnosis only'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (root / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize_attempt(args.attempt, args.output)))
