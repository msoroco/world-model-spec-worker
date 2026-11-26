"""Recorded-only crosswalk measurement; no legal or physical acceptance verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from measure_crosswalk import measure

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def crosswalk_observation(attempt):
    config = json.loads(required(attempt, 'config.json').read_text())
    from worker_exchange.native_output import provenance_record
    provenance = provenance_record(attempt)
    kind = 'original_native' if provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture'] else 'synthetic_cpu'
    return measure(attempt, config['case_id'], source_kind=kind)


def decoded_frames(path):
    call = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if call.returncode or not call.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + path.name)
    return int(call.stdout.strip())


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Choose a fresh recorded-only attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('frames') != 600:
        raise ValueError('Crosswalk capture contract differs')
    observed = crosswalk_observation(attempt)
    provenance = provenance_record(attempt)
    source_names = ('crosswalk-source.json', 'actor-sources.jsonl',
                    'camera-frames.jsonl', 'exception-context.json',
                    'road.xodr', 'video_frames.jsonl', 'trace.jsonl',
                    'capture/evidence.jsonl', 'capture/native/frames.jsonl')
    hashes = {name: sha(required(attempt, name)) for name in source_names}
    maps = source_rows(required(attempt, 'video_frames.jsonl'))
    actor = source_rows(required(attempt, 'actor-sources.jsonl'))
    camera = source_rows(required(attempt, 'camera-frames.jsonl'))
    trace = source_rows(required(attempt, 'trace.jsonl'))
    evidence = source_rows(required(attempt, 'capture/evidence.jsonl'))
    if len(maps) != 600 or len(actor) != 600 or len(camera) != 2400:
        raise ValueError('Crosswalk source frame count differs')
    if len(trace) != 600 or len(evidence) != 600:
        raise ValueError('Crosswalk Core source count differs')
    for index, (mapping, row, core, sensor) in enumerate(zip(maps, actor, trace, evidence)):
        if mapping.get('video_frame') != index or row.get('frame') != index:
            raise ValueError('Crosswalk source video join differs')
        if abs(mapping.get('time_s', -1) - row.get('time_s', -2)) > 1e-5:
            raise ValueError('Crosswalk source time join differs')
        if observed['source_kind'] == 'original_native' and mapping.get('native_frame') != row.get('native_frame'):
            raise ValueError('Original Native crosswalk frame join differs')
        footprint = row['ego_footprint_xy_m']
        center = row.get('center_xy_m') or [sum(point[axis] for point in footprint) / len(footprint)
                                            for axis in (0, 1)]
        if (core.get('frame') != mapping.get('native_frame') or
                sensor.get('original_frame') != mapping.get('native_frame') or
                any(abs(core['position_m'][axis] - center[axis]) > 1e-4 or
                    abs(sensor['ego']['position_m'][axis] - center[axis]) > 1e-4
                    for axis in (0, 1)) or
                abs(core['speed_mps'] - row['ego_speed_mps']) > 1e-4 or
                abs(sensor['ego']['speed_mps'] - row['ego_speed_mps']) > 1e-4):
            raise ValueError('Crosswalk footprint/Core/evidence spatial join differs')
    counts = {name: decoded_frames(required(attempt, name)) for name in VIDEOS}
    if set(counts.values()) != {600}:
        raise ValueError('Crosswalk source video count differs')
    context = json.loads(required(attempt, 'exception-context.json').read_text())
    if context.get('case_id') != config['case_id'] or context.get('legal_verdict') is not None:
        raise ValueError('Crosswalk exception context differs')
    native = observed['source_kind'] == 'original_native'
    recorded_values = {key: value for key, value in observed.items()
                       if key != 'legal_verdict'}
    channel = attempt / 'channels/crosswalk_observation.jsonl'
    channel.parent.mkdir(exist_ok=True)
    channel.write_text('\n'.join(json.dumps({'time_s': row['time_s'],
        'value': {'speed_mps': row['ego_speed_mps'],
                  'footprint_xy_m': row['ego_footprint_xy_m']}})
        for row in actor) + '\n')
    context_channel = attempt / 'channels/exception_authority.json'
    context_channel.write_text(json.dumps({'exception_authority': context}, indent=2) + '\n')
    result = {'case_id': config['case_id'], 'measured_values': recorded_values,
        'target_checks': [{'target': config['target_variant'],
            'requested': config['target_variant'], 'measured': recorded_values,
            'method': 'original source footprint/crosswalk polygon intersection',
            'tolerance': 'numeric geometry only; no legal threshold',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': ['crosswalk-source.json', 'actor-sources.jsonl']}],
        'setup_confirmed': native, 'behavior_attempted': native,
        'maneuver_completed': native and observed['rest_frames'] > 0,
        'termination_reason': '600 source frames retained',
        'physical_failure_flags': ['crosswalk_activity_and_exception_require_review'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'crosswalk_observation', 'unit': 'mixed',
                                'reference': 'channels/crosswalk_observation.jsonl'},
                               {'name': 'exception_authority', 'unit': 'structured',
                                'reference': 'channels/exception_authority.json'}],
        'realized_observables': {'crosswalk_overlap_m2': {
            'value': observed['max_footprint_overlap_m2'], 'unit': 'm2',
            'method': 'source polygon intersection', 'time_window': '600 frames',
            'statistic': 'maximum', 'reference': 'actor-sources.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c229397-crosswalk-analysis-v1', 'case_id': config['case_id'],
        'analysis_complete': True, 'legal_verdict_claimed': False,
        'measurements': {'crosswalk_observation': {
            'method': 'crosswalk_observation', 'value': observed,
            'sources': {name: hashes[name] for name in
                ('crosswalk-source.json', 'actor-sources.jsonl', 'camera-frames.jsonl',
                 'exception-context.json', 'road.xodr', 'video_frames.jsonl')} }},
        'source_hashes': hashes, 'source_video_frames': counts,
        'provenance': provenance,
        'limitations': ['Diagnostic fixture sources do not establish Native geometry or pixels.',
                        'Stop, stand, park and exceptions require independent authority review.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output)))
