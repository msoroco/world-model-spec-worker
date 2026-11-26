"""Saved-only route analysis and Native result, without physical/legal acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from route_measure import measure

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
SOURCES = ('route-trace.jsonl', 'route-context.json', 'road.xodr', 'video_frames.jsonl')


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def route_observation(folder):
    sources = [required(folder, name) for name in SOURCES]
    return {'method': 'route_observation',
            'value': measure(*(path.read_bytes() for path in sources)),
            'sources': {name: sha(path) for name, path in zip(SOURCES, sources)}}


def analysis_report(folder, contract=None):
    config = json.loads(required(folder, 'config.json').read_text())
    observation = route_observation(folder)
    facts = observation['value']
    if config['case_id'] != json.loads(required(folder, 'route-context.json').read_text())['case_id']:
        raise ValueError('exact case/source identity differs')
    if facts['authored_alternate_connected'] != config['alternate_possible']:
        raise ValueError('exact case route topology differs')
    return {'format': 'c230259-route-analysis-v1', 'case_id': config['case_id'],
            'analysis_complete': True, 'legal_verdict_claimed': False,
            'measurements': {'route_observation': observation},
            'limitations': ['Authored road connectivity does not prove legal or practical route availability.',
                            'Legal controlled-access designation and actual impediment require independent review.',
                            'CPU diagnostics cannot prove physical pixels or CARLA motion.']}


def decoded_frames(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Original camera full decode failed: ' + path.name)
    return int(result.stdout.strip())


def verify_joins(folder):
    names = ('trace.jsonl', 'capture/evidence.jsonl',
             'capture/native/frames.jsonl', 'video_frames.jsonl', 'route-trace.jsonl')
    rows = [[json.loads(line) for line in required(folder, name).read_text().splitlines()]
            for name in names]
    if any(len(part) != 900 for part in rows):
        raise ValueError('Original Core/evidence/route frame count differs')
    for core, evidence, graph, frame, route in zip(*rows):
        native = frame['native_frame']
        if any(item.get(key) != native for item, key in
               ((core, 'frame'), (evidence, 'original_frame'),
                (graph, 'frame'), (route, 'native_frame'))):
            raise ValueError('Original Core/evidence/route frame join differs')
        if max(abs(item.get(key, -999) - frame['time_s']) for item, key in
               ((core, 'time_s'), (evidence, 'recording_time_s'),
                (route, 'time_s'))) > .005:
            raise ValueError('Original Core/evidence/route time join differs')
    return {name: sha(required(folder, name)) for name in names}


def derive_channels(folder):
    rows = [json.loads(line) for line in required(folder, 'route-trace.jsonl').read_text().splitlines()]
    channels = {'participant_motion': [], 'route_occupancy': []}
    for row in rows:
        channels['participant_motion'].append({'time_s': row['time_s'],
            'value': {'ego': row['ego'], 'following': row['following']}})
        channels['route_occupancy'].append({'time_s': row['time_s'],
            'value': {'ego_road_id': row['ego']['road_id'],
                      'following_road_ids': [f['road_id'] for f in row['following']]}})
    result = {}
    destination = Path(folder) / 'channels'
    destination.mkdir(exist_ok=True)
    for name, content in channels.items():
        path = destination / (name + '.jsonl')
        if path.exists():
            raise ValueError('Derived channel already exists: ' + name)
        path.write_text(''.join(json.dumps(item, allow_nan=False) + '\n' for item in content))
        result[name] = str(path.relative_to(folder))
    return result


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use fresh analysis path; retain original source')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('Exact original route capture contract changed')
    report = analysis_report(attempt)
    facts = report['measurements']['route_observation']['value']
    joins = verify_joins(attempt)
    video_counts = {name: decoded_frames(required(attempt, name)) for name in VIDEOS}
    if set(video_counts.values()) != {900}:
        raise ValueError('Original four-camera duration differs')
    provenance = provenance_record(attempt)
    native = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    channels = derive_channels(attempt)
    requested = {'alternate_possible': config['alternate_possible'],
                 'take_alternate': config['take_alternate']}
    measured = {'authored_alternate_connected': facts['authored_alternate_connected'],
                'observed_alternate_road': facts['observed_alternate_road'],
                'observed_destination_road': facts['observed_destination_road'],
                'immediately_following_approach_frames':
                    facts['immediately_following_approach_frames']}
    result = {'case_id': config['case_id'], 'measured_values': facts,
        'target_checks': [{'target': 'slow driver and immediately following traffic at an alternate route opportunity',
            'requested': requested, 'measured': measured,
            'method': 'original Native participant positions, map road IDs, saved route context and same-frame cameras',
            'tolerance': 'continuous observed values; no legal threshold',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': list(SOURCES)}],
        'setup_confirmed': native and facts['controlled_access_designation_independently_verified'],
        'behavior_attempted': native, 'maneuver_completed': False,
        'termination_reason': '900 original Native frames retained',
        'physical_failure_flags': ['controlled_access_designation_requires_independent_source',
            'route_usability_and_impediment_require_independent_review',
            'camera_pixels_and_trajectory_require_physical_review'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': name, 'unit': 'structured', 'reference': reference}
            for name, reference in channels.items()],
        'realized_observables': {'alternate_route_road_observed_frames': {
            'value': facts['observed_alternate_road_frames'], 'unit': 'count',
            'method': 'original map road ID joined to vehicle and camera frames',
            'time_window': '900 frames', 'statistic': 'count of original road 3 occupancy',
            'reference': 'route-trace.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report.update(original_joins=joins, source_video_frames=video_counts,
                  provenance=provenance)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
