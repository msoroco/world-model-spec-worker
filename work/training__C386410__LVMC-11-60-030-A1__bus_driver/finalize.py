"""Saved-only, source-bound bus standing measurements without a legal verdict."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'analysis'))
from bus_standing import CAMERAS, measure_saved

SOURCES = ('road.xodr', 'bus-context.json', 'bus-history.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           *(name + '.mkv' for name in CAMERAS))


def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def measure_bus_event(root):
    source_kind = 'synthetic_native_sample' if (root / 'diagnostic-input.json').is_file() else 'original_native'
    return measure_saved(root, source_kind=source_kind)


def source_place(root):
    context = json.loads(required(root, 'bus-context.json').read_text())
    return {'street_id': context['street_id'], 'zone': context['zone'],
            'official_designation_verified': context.get('official_designation_verified') is True,
            'native_lane_readback': context.get('native_lane_readback', [])}


def source_scope(root):
    context = json.loads(required(root, 'bus-context.json').read_text())
    return {'vehicle_class': context['vehicle_class'], 'route_id': context['route_id'],
            'vehicle_class_verified': context.get('vehicle_class_verified') is True,
            'route_assignment_verified': context.get('route_assignment_verified') is True,
            'driver_presence_verified': context.get('driver_presence_verified') is True}


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Fresh saved-only bus finalization required')
    for name in ('config.json', 'construction.json', *SOURCES):
        required(attempt, name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('case_id')
    if (case != construction.get('case_id') or case != config.get('selected_case_id') or
            case not in config.get('supported_case_ids', [])):
        raise ValueError('Exact bus case changed')
    context = json.loads((attempt / 'bus-context.json').read_text())
    frame_map, history, trace = [rows(attempt / name) for name in
                                 ('video_frames.jsonl', 'bus-history.jsonl', 'trace.jsonl')]
    if len(frame_map) != len(history) or len(frame_map) != len(trace) or len(frame_map) != 600:
        raise ValueError('Original 600-frame bus source join incomplete')
    for i, (mapped, pose, state) in enumerate(zip(frame_map, history, trace)):
        if (mapped.get('video_frame') != pose.get('video_frame') or
                pose.get('video_frame') != i or mapped.get('native_frame') != pose.get('native_frame') or
                mapped.get('native_frame') != state.get('frame') or
                abs(mapped.get('time_s', -10) - pose.get('time_s', -20)) > .005 or
                abs(mapped.get('time_s', -10) - state.get('time_s', -20)) > .005):
            raise ValueError('Original bus trace/frame/time join differs')
    event = measure_bus_event(attempt)
    place = source_place(attempt)
    scope = source_scope(attempt)
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for spec in config['recording_description']['channels']:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row in history:
                values = {
                    'ru.bus': {'actor_id': row.get('actor_id'), 'blueprint_id': row.get('blueprint_id'),
                               'vehicle_class': context['vehicle_class']},
                    'kin.velocity': {'speed_mps': row['bus_speed_mps']},
                    'kin.time': {'native_frame': row['native_frame'], 'time_s': row['time_s']},
                    'st.curb_zone': place,
                    'st.transit_stop': {'zone_kind': context['zone']['kind'],
                                        'designation_verified': place['official_designation_verified']},
                    'dev.regulatory_sign': {'source': context['zone'].get('designation_source'),
                                            'official_designation_verified': place['official_designation_verified']},
                    'drv.standing_or_parked': {'stationary_speed_probe': row['bus_speed_mps'] <= .1,
                                               'brake_applied': row['parking_brake_applied'],
                                               'legal_interpretation': 'unresolved'},
                    'rel.occupies': {'zone_id': row['occupied_zone_id'],
                                     'zone_kind': context['zone']['kind']},
                    'st.roadway': {'street_id': context['street_id'],
                                   'street_status_verified': context.get('street_status_verified') is True},
                }
                if name not in values:
                    raise ValueError('Unknown recorded bus channel: ' + name)
                stream.write(json.dumps({'time_s': row['time_s'], 'value': values[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': spec['unit'], 'reference': 'channels/' + path.name})
    evidence.append({'name': 'route_designation_source', 'unit': 'structured',
                     'reference': 'bus-context.json'})
    measurements = {
        'bus_event': {'method': 'measure_bus_event', 'value': event, 'sources': source_hashes},
        'bus_place': {'method': 'source_place', 'value': place, 'sources': source_hashes},
        'bus_scope': {'method': 'source_scope', 'value': scope, 'sources': source_hashes},
    }
    report = {'format': 'worker-analysis-report-v1', 'case_id': case,
              'measurements': measurements, 'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False}
    result = {'case_id': case, 'measured_values': event,
              'target_checks': [{'target': 'source-measured stationary bus occupancy',
                'requested': config['requested_location'],
                'measured': event['zone_kind_observed'],
                'method': 'Original frame-joined bus motion and zone readback',
                'tolerance': 'exact category',
                'matched': event['zone_kind_observed'] == config['requested_location'],
                'physical_cause_confirmed': False, 'cause_evidence': list(source_hashes)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'saved original source diagnostic',
              'physical_failure_flags': ['Physical event and designation require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if
                  (attempt / 'diagnostic-input.json').is_file() else 'original_native',
              'accepted': False, 'legal_verdict_claimed': False}
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(attempt)
    repo = next((p for p in Path(__file__).resolve().parents if (p / 'batch.json').is_file()), None)
    if repo is None:
        raise ValueError('Worker runtime root unavailable')
    sys.path.insert(0, str(repo / 'runtime' / 'scenario_pipeline'))
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))


if __name__ == '__main__':
    main()
