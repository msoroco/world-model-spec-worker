"""Draft source-bound Native finalization for the C179480 primary pair.

This retains measured motion and explicitly withholds physical/legal acceptance.
Selected-case compatibility and independent traffic/exception review are pending.
"""
import argparse
import json
from pathlib import Path
import sys

from native_channels import CHANNELS, channels_for, derive
from saved_analysis import CAMERAS, review, sha256
from source_measurement import analyze_hazard, analyze_control, load_rows, measure
from source_provenance import classify, ORIGINAL, SYNTHETIC
from sweep_case import resolve
from control_phase_measurement import measure_red_onset


ASSIGNMENT = 'training__C179480__NRS-484B-627-2__motor_vehicle_driver'
EXPECTED_OVERLAP = {'reference': True, 'contrast': False,
                    'safe_operation_stop': True, 'law_required_stop': True}


def _native_writer():
    try:
        from worker_exchange.native_output import write_result
    except ModuleNotFoundError:
        repo = Path(__file__).resolve().parents[2]
        runtime = str(repo/'runtime/pipeline/scenario_pipeline')
        if runtime not in sys.path:
            sys.path.insert(0, runtime)
        from worker_exchange.native_output import write_result
    return write_result


def measure_roadway_stop(measured, source_hashes):
    return {
        'value': {
            'complete_stop_observed': measured['complete_stop_observed'],
            'roadway_stop_frames': measured['roadway_stop_frames'],
            'roadway_lane_overlap_frames': measured['roadway_lane_overlap_frames'],
            'following_speed_drop_mps': measured['following_speed_drop_mps'],
            'normal_reasonable_movement_impeded':
                measured['normal_reasonable_movement_impeded'],
        },
        'method': 'measure_roadway_stop',
        'sources': {name: source_hashes[name] for name in
                    ('native-actors.jsonl','video_frames.jsonl')},
    }


def measure_paved_roadway_scope(map_readback, measured, source_hashes):
    return {
        'value': {
            'map_name': map_readback['map_name'],
            'road_id': map_readback['road_id'],
            'lane_id': map_readback['lane_id'],
            'roadway_stop_observed': bool(measured['roadway_stop_frames']),
            'paved_surface_verified': False,
        },
        'method': 'measure_paved_roadway_scope',
        'sources': {name: source_hashes[name] for name in
                    ('native-map-readback.json','native-actors.jsonl')},
    }


def finalize(attempt, output):
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    source_kind = classify(attempt)
    source_label = ('diagnostic synthetic' if source_kind == SYNTHETIC
                    else 'original')
    config = json.loads((attempt/'config.json').read_text())
    case = config.get('case_suffix')
    base, axis, value = resolve(config)
    if (case not in EXPECTED_OVERLAP
            or base != case
            or config.get('law_id') != 'NRS-484B-627-2'
            or config.get('rate_hz') != 20):
        raise ValueError('Finalizer requires an exact C179480 primary case config')
    names = [entry.get('name') for entry in
             config.get('recording_description', {}).get('channels', [])]
    expected_channels = channels_for(case, axis)
    if set(names) != set(expected_channels) or len(names) != len(expected_channels):
        raise ValueError('Recording description differs from source channels')
    if (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    map_path = attempt/'native-map-readback.json'
    if not map_path.is_file():
        raise ValueError('Missing required source: native-map-readback.json')
    map_readback = json.loads(map_path.read_text())
    if (map_readback.get('case') != case or map_readback.get('sweep_axis') != axis
            or (axis is not None and map_readback.get('sweep_value') != value)):
        raise ValueError('Original map readback belongs to another case')
    rows = load_rows(attempt/'native-actors.jsonl', attempt/'video_frames.jsonl')
    if source_kind == SYNTHETIC and not (attempt/'source-measurements.json').exists():
        if any(row.get('source_kind') != SYNTHETIC for row in rows):
            raise ValueError('Diagnostic actor source provenance differs')
        receipt = measure(rows)
        receipt.update(format='c179480-source-measurements-v1',case=case,
                       actor_source_sha256=sha256(attempt/'native-actors.jsonl'),
                       frame_map_sha256=sha256(attempt/'video_frames.jsonl'),
                       map_readback_sha256=sha256(map_path))
        if case == 'safe_operation_stop':
            receipt['hazard_observation'] = analyze_hazard(
                attempt/'native-actors.jsonl',attempt/'video_frames.jsonl',
                source_kind=SYNTHETIC)
        if case == 'law_required_stop':
            receipt['governing_control_observation'] = analyze_control(
                attempt/'native-actors.jsonl',attempt/'video_frames.jsonl',
                expected_control_id=map_readback.get('surveyed_governing_traffic_light_id'),
                source_kind=SYNTHETIC)
            if axis == 'governing_red_onset_s':
                receipt['governing_phase_observation'] = measure_red_onset(
                    attempt/'native-actors.jsonl',attempt/'video_frames.jsonl',
                    expected_control_id=map_readback.get('surveyed_governing_traffic_light_id'),
                    source_kind=SYNTHETIC)
        with (attempt/'source-measurements.json').open('x') as stream:
            json.dump(receipt,stream,allow_nan=False)
            stream.write('\n')
    mapping = [json.loads(line) for line in
               (attempt/'video_frames.jsonl').read_text().splitlines() if line.strip()]
    if any(row.get('video_frame') != index for index, row in enumerate(rows)):
        raise ValueError('Original actor video-frame identity differs')
    if any(b['frame']-a['frame'] != 1 or
           abs(y['time_s']-x['time_s']-.05) > .001
           for a,b,x,y in zip(rows,rows[1:],mapping,mapping[1:])):
        raise ValueError('Original 20 Hz Native frame continuity differs')
    # Verify all original source hashes and camera decodes before creating any
    # derived Native output. The saved report itself is written only once.
    report = review(attempt, output, write=False)
    if config.get('duration_s') != len(rows)/20:
        raise ValueError('Original source duration differs from config')
    derived = derive(attempt)
    trace_text = ''
    for actor, frame in zip(rows, mapping):
        trace = {'frame': actor['frame'], 'time_s': frame['time_s'],
                 'position_m': [actor['ego_x_m'], actor['ego_y_m']],
                 'position': {'x': actor['ego_x_m'],
                              'y': actor['ego_y_m'], 'z': 0.0},
                 'heading_deg': actor['ego_yaw_deg'],
                 'speed_mps': actor['ego_speed_mps'],
                 'speed_mph': actor['ego_speed_mps'] / .44704,
                 'velocity_mps': actor['ego_velocity_xyz_mps'],
                 'control': {},
                 'speed_provenance': 'synthetic_native_sample' if source_kind == SYNTHETIC else 'original_carla_velocity',
                 'source_actor_sha256': report['source_sha256']['native-actors.jsonl']}
        trace_text += json.dumps(trace, allow_nan=False)+'\n'
    trace_path = attempt/'trace.jsonl'
    if trace_path.exists():
        if trace_path.read_text() != trace_text:
            raise ValueError('Saved trace differs from current raw sources')
    else:
        trace_path.write_text(trace_text)
    measured = report['measured_values']
    contexts = config['recording_description']['context_inputs']
    if contexts:
        context_text = json.dumps({entry['name']: {
                'map_name':map_readback['map_name'],
                'road_id':map_readback['road_id'],
                'lane_id':map_readback['lane_id'],
                'source_sha256':report['source_sha256']['native-map-readback.json'],
                'provenance_kind':report['provenance_kind'],
            } for entry in contexts},allow_nan=False)+'\n'
        context_path = attempt/'recorded-context.json'
        if context_path.exists():
            if context_path.read_text() != context_text:
                raise ValueError('Saved context differs from current map source')
        else:
            context_path.write_text(context_text)
    overlap = bool(measured['roadway_lane_overlap_frames'])
    stopped = measured['complete_stop_observed']
    matched = stopped and overlap == EXPECTED_OVERLAP[case]
    hazard = report.get('hazard_observation')
    control = report.get('governing_control_observation')
    if case == 'safe_operation_stop' and (
            not hazard or hazard['sample_count'] != len(rows)):
        raise ValueError('Safe-operation original hazard observation absent')
    if case == 'law_required_stop' and (
            not control or control['sample_count'] != len(rows)):
        raise ValueError('Law-required original control observation absent')
    if case == 'law_required_stop':
        matched = matched and control['source_visible_stop_requirement']
    target = {
        'target': ('sampled complete roadway stop with associated red control'
                   if case == 'law_required_stop' else
                   'sampled complete stop with requested travel-lane footprint overlap'),
        'requested': EXPECTED_OVERLAP[case], 'measured': overlap,
        'method': ('diagnostic synthetic actor/body/lane and synchronized frame map'
                   if source_kind == SYNTHETIC else
                   'original actor velocity/body/lane and synchronized frame map'),
        'tolerance': '0.05 m/s engineering stop tolerance; no legal threshold',
        'matched': matched, 'physical_cause_confirmed': False,
        'cause_evidence': ['native-actors.jsonl','video_frames.jsonl',
                           'native-map-readback.json'],
    }
    source_hashes = dict(report['source_sha256'])
    source_hashes['trace.jsonl'] = sha256(attempt/'trace.jsonl')
    sources = {name: source_hashes[name] for name in
               ('native-actors.jsonl','video_frames.jsonl','native-map-readback.json')}
    checks = {name: {'status': 'unverified', 'method': method,
                     'sources': sources, 'intervals': [],
                     'legal_verdict_claimed': False,
                     'physical_causation_claimed': False}
              for name, method in (
                  ('setup','independent roadway/map and camera visibility review'),
                  ('target',source_label+' sampled stop and lane-footprint review'),
                  ('maneuver','independent normal-and-reasonable traffic effect and exception review'))}
    checks['target']['status'] = 'met' if matched else 'not_met'
    result = {
        'case_id': config['case_id'],
        'measured_values': measured,
        'target_checks': [target],
        'setup_confirmed': False,
        'behavior_attempted': True,
        'maneuver_completed': False,
        'physical_checks': checks,
        'termination_reason': 'full '+source_label+' attempt retained',
        'physical_failure_flags': ['traffic_impediment_and_exceptions_unreviewed']+
                                  (['safe_operation_necessity_unreviewed']
                                   if case == 'safe_operation_stop' else [])+
                                  (['law_compliance_unreviewed']
                                   if case == 'law_required_stop' else [])+
                                  ([] if matched else ['sampled_stop_target_not_met']),
        'trace_reference': 'trace.jsonl',
        'video_references': [name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [
            {'name': entry['name'], 'unit': entry['unit'],
             'reference': 'channels/'+entry['name']+'.jsonl'}
            for entry in config['recording_description']['channels']] + [
            {'name': entry['name'], 'unit': entry['unit'],
             'reference': 'recorded-context.json'}
            for entry in config['recording_description']['context_inputs']],
        'realized_observables': {
            'sampled_roadway_lane_overlap': {
                'value': len(measured['roadway_lane_overlap_frames']), 'unit': 'count',
                'method': 'source-joined stopped actor body and driving-lane readback',
                'time_window':'full 30-second source trace','statistic':'frame_count',
                'reference': 'channels/ego_lane_footprint.jsonl'},
            'following_speed_drop': {
                'value': measured['following_speed_drop_mps'],
                'unit': 'm/s',
                'method': 'source-joined '+source_label+' ego/follower actor and frame rows',
                'time_window':'full 30-second source trace','statistic':'initial_minus_minimum',
                'reference': 'channels/traffic_effect_evidence.jsonl'}},
        'provenance_kind': 'synthetic_fixture' if source_kind == SYNTHETIC else 'native',
        'diagnostic_fixture': source_kind == SYNTHETIC,
        'accepted': False, 'legal_verdict_claimed': False,
    }
    if hazard is not None:
        result['realized_observables']['minimum_source_visible_hazard_gap'] = {
            'value': hazard['minimum_ego_center_gap_m'], 'unit': 'm',
            'method': source_label+' actor body, lane, velocity and gap rows',
            'time_window':'full 30-second source trace','statistic':'minimum',
            'reference': 'channels/ego_hazard_gap_history.jsonl'}
    if control is not None:
        result['realized_observables']['source_visible_red_control_frames'] = {
            'value': len(control['associated_red_frames']), 'unit': 'count',
            'method': source_label+' traffic-light actor and ego association readback',
            'time_window':'full 30-second source trace','statistic':'frame_count',
            'reference': 'channels/governing_control_readback.jsonl'}
    if axis is None:
        raise ValueError('Sweep finalizer requires an exact controlled axis')
    definition = config.get('sweep_measurement')
    if (not isinstance(definition, dict) or
            definition.get('variable') != axis or
            definition.get('observable') != axis or
            definition.get('unit') not in ('m', 's') or
            not isinstance(definition.get('measurement'), dict)):
        raise ValueError('Sweep measurement differs from the frozen case')
    measurement = definition['measurement']
    if measurement.get('statistic') not in ('min', 'first') or any(
            not measurement.get(key) for key in ('method', 'time_window')):
        raise ValueError('Sweep measurement procedure is incomplete')
    channel_path = attempt/'channels'/(axis+'.jsonl')
    channel = [json.loads(line) for line in channel_path.read_text().splitlines()]
    if len(channel) != len(rows) or any(
            sample.get('time_s') != frame['time_s'] or
            type(sample.get('value')) not in (int, float)
            for sample, frame in zip(channel, mapping)):
        raise ValueError('Source-derived sweep channel lacks exact Native frame joins')
    values = [sample['value'] for sample in channel]
    result['realized_observables'][axis] = {
        'value': min(values) if measurement['statistic'] == 'min' else values[0],
        'unit': definition['unit'], 'method': measurement['method'],
        'time_window': measurement['time_window'],
        'statistic': measurement['statistic'],
        'sample_window_s': [channel[0]['time_s'], channel[-1]['time_s']],
        'reference': 'channels/'+axis+'.jsonl'}
    _native_writer()(attempt, result)
    report['derived_channels'] = derived
    report['trace_sha256'] = source_hashes['trace.jsonl']
    report['native_result_sha256'] = sha256(attempt/'result.json')
    report['measurements'] = {
        'roadway_stop': measure_roadway_stop(measured, source_hashes),
        'paved_roadway_scope': measure_paved_roadway_scope(
            map_readback, measured, source_hashes),
    }
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()
