"""Source-bound finalization of the complete truck-route journey; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_through_route import measure, rows
from measure_purpose_route import measure_purpose

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: '+path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_complete_passage(observation):
    return bool(observation['complete_truck_to_truck_passage'] and observation['vehicle_is_truck_reviewed'] and
                observation['enroute_purpose_reviewed'] == 'none')


def measure_service_passage(observation):
    return bool(observation['complete_truck_to_truck_passage'] and observation['vehicle_is_truck_reviewed'] and
                observation['enroute_purpose_reviewed'] in ('pickup', 'delivery', 'essential') and
                observation['reviewed_service_stop_frames'] >= 100)


def write_channel(path, mapping, trace, name):
    total = 0.0
    previous = None
    with path.open('x') as stream:
        for frame, source in zip(mapping, trace):
            xy = (source['ego_x_m'], source['ego_y_m'])
            if previous is not None:
                total += ((xy[0]-previous[0])**2+(xy[1]-previous[1])**2)**.5
            previous = xy
            value = {
                'kin.position': {'x_m': xy[0], 'y_m': xy[1]},
                'kin.path_length': total,
                'drv.standing_or_parked': source['ego_speed_mps'] <= .05,
                'st.roadway': {'road_id': source['road_id']},
            }[name]
            stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}, allow_nan=False)+'\n')


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    config = json.loads((attempt/'config.json').read_text())
    case_id = config['case_id']
    sha(attempt/'route_context.json')
    if case_id.endswith('__probe_01'):
        observation = measure(attempt)
        method, key = measure_complete_passage, 'complete_truck_route_passage'
    elif case_id.endswith('__probe_02'):
        observation = measure_purpose(attempt)
        method, key = measure_service_passage, 'documented_service_passage'
    else:
        raise ValueError('Wrong exact through-route case')
    for name in ('video_frames.jsonl', 'native_route_trace.jsonl', 'route_context.json',
                 'trace.jsonl', *[n+'.mkv' for n in CAMERAS]):
        sha(attempt/name)
    mapping = rows(attempt/'video_frames.jsonl')
    trace = rows(attempt/'native_route_trace.jsonl')
    if len(mapping) != len(trace):
        raise ValueError('Source trace/frame count differs')
    channel_dir = attempt/'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    description = config['recording_description']
    for channel in description['channels']:
        name = channel['name']
        ref = 'channels/'+name+'.jsonl'
        write_channel(attempt/ref, mapping, trace, name)
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': ref})
    context = json.loads((attempt/'route_context.json').read_text())
    reviewed = {'dev.regulatory_sign': {
                    'entry_truck_route_id': context['entry_truck_route_id'],
                    'intervening_street_id': context['intervening_street_id'],
                    'exit_truck_route_id': context['exit_truck_route_id'],
                    'truck_route_designation_source': context['truck_route_designation_source'],
                    'nontruck_street_designation_source': context['nontruck_street_designation_source']},
                'ru.truck': {'vehicle_is_truck': context['vehicle_is_truck'],
                             'ego_actor_id': context['ego_actor_id'],
                             'truck_blueprint_source': context['truck_blueprint_source']},
                'st.driveway_or_alley_entrance': {
                    'served_premises_source': context['served_premises_source'],
                    'enroute_purpose': context['enroute_purpose'],
                    'enroute_purpose_source': context['enroute_purpose_source']}}
    context_path = attempt/'reviewed-route-context.json'
    context_path.write_text(json.dumps(reviewed, allow_nan=False)+'\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': context_path.name})
    matched = method(observation)
    result = {
        'case_id': case_id, 'measured_values': {'through_route': observation},
        'target_checks': [{'target': 'complete three-road journey with reviewed enroute purpose',
                           'requested': True, 'measured': matched,
                           'method': 'saved original route/vehicle/purpose source join',
                           'tolerance': 0, 'matched': matched,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['native_route_trace.jsonl', 'route_context.json']}],
        'setup_confirmed': matched, 'behavior_attempted': matched,
        'maneuver_completed': observation['complete_truck_to_truck_passage'],
        'termination_reason': 'saved original 30-second route trace analyzed',
        'physical_failure_flags': [] if matched else ['reviewed_route_or_purpose_target_unconfirmed'],
        'trace_reference': 'trace.jsonl', 'video_references': [name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}, 'accepted': False,
        'provenance_kind': ('synthetic_fixture' if context['review_kind']=='synthetic_diagnostic' else 'native'),
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    source_names = ('native_route_trace.jsonl', 'route_context.json', 'video_frames.jsonl')
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {key: {'value': matched, 'method': method.__name__,
                                     'sources': {name: sha(attempt/name) for name in source_names}}},
              'measurement_summary': observation,
              'limitations': ['Source review and synthetic diagnostics do not establish physical or legal acceptance']}
    from worker_exchange.native_output import validate_result, physical_result
    validate_result(result)
    result = physical_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))
