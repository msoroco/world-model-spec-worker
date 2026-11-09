"""Saved-only finalizer for the C101303 following / lane-change cases.

Reads only original acquisition files in --attempt and writes analysis-report.json
and result.json. It never contacts CARLA, rewrites an input or evaluates law:
'reasonable and prudent' is not measured, and no gap/speed value is a threshold.
"""
import argparse
import json
import math
import sys
from pathlib import Path

REQUIRED = ('config.json', 'following_samples.jsonl', 'surface_context.json', 'trace.jsonl', 'video_frames.jsonl')


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def stats(values):
    if not values or not all(finite(v) for v in values):
        raise ValueError('No finite samples to summarize')
    return {'min': min(values), 'max': max(values), 'mean': sum(values) / len(values), 'first': values[0], 'last': values[-1], 'count': len(values)}


def public_way_context(ctx, samples):
    return {'declared_public_way_road_ids': ctx['public_way_road_ids'], 'sampled_road_ids': sorted({r['ego_road_id'] for r in samples}),
            'basis': 'authored synthetic road declaration plus native readback road id; dedication and availability are declared, not measured'}


def speed_profile(ctx, samples):
    return {'ego_speed_mps': stats([r['ego_speed_mps'] for r in samples]), 'lead_speed_mps': stats([r['lead_speed_mps'] for r in samples]),
            'unit': 'm/s', 'scope': 'original live actor velocity telemetry; no reasonable-and-prudent cutoff'}


def separation_profile(ctx, samples):
    gaps = [r['bumper_gap_m'] for r in samples if r['bumper_gap_m'] is not None]
    return dict(stats(gaps), unit='m', definition='longitudinal distance between lead rear and ego front along the road while the lead is ahead in the ego lane',
                frames_with_lead_ahead_in_lane=len(gaps), frames_total=len(samples))


def surrounding_traffic(ctx, samples):
    queued = any(r.get('queued_s_m') is not None for r in samples)
    return {'other_vehicles_recorded': 1 + int(queued), 'lead_present': True, 'queued_vehicle_present': queued,
            'pedestrians_or_cyclists_recorded': 0, 'scope': 'participants authored by this construction'}


def highway_condition(ctx, samples):
    return {'surface': ctx['surface'], 'grade': ctx['grade'], 'crest_s_m': ctx['crest_s_m'], 'crest_vertical_curve_m': ctx['crest_vertical_curve_m'],
            'lane_width_m': ctx['lane_width_m'], 'ego_pitch_deg': stats([r['ego_pitch_deg'] for r in samples]),
            'ego_elevation_m': stats([r['ego_elevation_m'] for r in samples])}


def following_interval(ctx, samples):
    start = ctx['lane_change_start_frame_index'] if 'lane_change_start_frame_index' in ctx else None
    transition = next((i for i, r in enumerate(samples) if i and r['ego_lane_id'] != samples[0]['ego_lane_id']), None)
    end_index = transition if transition is not None else len(samples)
    following = [i for i in range(end_index) if samples[i]['lead_in_ego_lane']]
    if not following:
        raise ValueError('No following interval before a lane change in the recording')
    contiguous = all(b == a + 1 for a, b in zip(following, following[1:]))
    return {'first_frame': samples[following[0]]['frame'], 'last_frame': samples[following[-1]]['frame'],
            'duration_s': samples[following[-1]]['time_s'] - samples[following[0]]['time_s'], 'contiguous': contiguous,
            'lane_transition_frame': None if transition is None else samples[transition]['frame'],
            'initial_lane_id': samples[0]['ego_lane_id'], 'duration_is_not_a_legal_threshold': True}


def lane_change_route(ctx, samples):
    transition = next((i for i, r in enumerate(samples) if i and r['ego_lane_id'] != samples[0]['ego_lane_id']), None)
    first_offset = next((i for i, r in enumerate(samples) if r['ego_s_m'] >= ctx['lane_change_trigger_s_m']), None)
    if transition is None or first_offset is None:
        raise ValueError('No lane change observed in original lane readback')
    lo, hi = ctx['crest_s_m'] - ctx['crest_vertical_curve_m'] / 2, ctx['crest_s_m'] + ctx['crest_vertical_curve_m'] / 2
    s_start, s_end = samples[first_offset]['ego_s_m'], samples[-1]['ego_s_m']
    return {'from_lane': samples[0]['ego_lane_id'], 'to_lane': samples[-1]['ego_lane_id'], 'lane_readback_transition_frame': samples[transition]['frame'],
            'route_s_start_m': s_start, 'route_s_end_m': s_end, 'crest_span_s_m': [lo, hi],
            'route_contains_crest_apex': s_start <= ctx['crest_s_m'] <= s_end, 'crest_apex_s_m': ctx['crest_s_m'],
            'crest_crossed_during_lane_change': samples[transition]['ego_s_m'] >= lo}


def qualifying_motion(ctx, samples):
    moving = lambda key: sum(1 for r in samples if r[key] > 0.5)
    return {'ego_moving_frames': moving('ego_speed_mps'), 'lead_moving_frames': moving('lead_speed_mps'), 'frames_total': len(samples),
            'moving_threshold_mps': 0.5, 'threshold_is_engineering_only': True,
            'vehicle_class': 'vehicle.tesla.model3 motor vehicles, driver identity authored'}


METHODS = {'public_way_context': public_way_context, 'speed_profile': speed_profile, 'separation_profile': separation_profile,
           'surrounding_traffic': surrounding_traffic, 'highway_condition': highway_condition, 'following_interval': following_interval,
           'lane_change_route': lane_change_route, 'qualifying_motion': qualifying_motion}


def target_checks(config, ctx, samples, root):
    params, tolerance = ctx['case_parameters'], 1.0
    first = samples[0]
    checks = []

    def add(name, requested, measured, method, tol, cause):
        checks.append({'target': name, 'requested': requested, 'measured': measured, 'method': method, 'tolerance': tol,
                       'matched': abs(requested - measured) <= tol, 'physical_cause_confirmed': False, 'cause_evidence': cause})
    add('initial_ego_speed_mps', params['ego_set_speed_mps'], first['ego_speed_mps'], 'first sampled live actor speed', 1.5, 'following_samples.jsonl')
    add('initial_lead_speed_mps', params['lead_speed_mps'], first['lead_speed_mps'], 'first sampled live actor speed', 1.5, 'following_samples.jsonl')
    gap = first['bumper_gap_m']
    if gap is None:
        raise ValueError('Initial frame lacks a lead ahead in the ego lane')
    add('initial_bumper_gap_m', params['initial_gap_m'], gap, 'first-frame road-frame bumper gap', 2.0, 'following_samples.jsonl')
    evidence = Path(root) / 'capture/evidence.jsonl'
    if evidence.is_file() and params['wetness'] > 0:
        wet = [json.loads(line)['world']['weather']['wetness'] for line in evidence.read_text().splitlines() if line.strip()]
        add('weather_wetness', params['wetness'], sum(wet) / len(wet), 'native weather readback each frame', 1.0, 'capture/evidence.jsonl')
    return checks


def analyze(root):
    root = Path(root)
    for name in REQUIRED:
        need(root, name)
    config = json.loads((root / 'config.json').read_text())
    ctx = json.loads((root / 'surface_context.json').read_text())
    samples = rows(root / 'following_samples.jsonl')
    if len(samples) < 2:
        raise ValueError('Insufficient following samples')
    contract = json.loads((root / 'measurement-contract.json').read_text()) if (root / 'measurement-contract.json').is_file() else None
    method_inputs = config['measurement_inputs']
    measurements = {}
    for key, spec in method_inputs.items():
        value = METHODS[spec['method']](ctx, samples)
        measurements[key] = {'method': spec['method'], 'value': value, 'sources': {name: sha(need(root, name)) for name in spec['inputs']}}
    checks = target_checks(config, ctx, samples, root)
    description = config['case']['recording_description']
    evidence = []
    for channel in description['channels']:
        evidence.append({'name': channel['name'], 'unit': channel['unit'], 'reference': 'channels/' + channel['name'] + '.jsonl'})
    for context in description['context_inputs']:
        evidence.append({'name': context['name'], 'unit': context['unit'], 'reference': 'surface_context.json'})
    result = {'case_id': config['selected_case_id'], 'measured_values': {k: v['value'] for k, v in measurements.items()}, 'target_checks': checks,
              'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'pending physical assessment', 'physical_failure_flags': {'detection_validated': False},
              'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence, 'realized_observables': {}}
    from worker_exchange.native_output import physical_result, write_result
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'], 'measurements': measurements,
            'physical_checks': result['physical_checks'], 'realized_observables': result['realized_observables'], 'analysis_complete': True,
            'limitations': ['No legal judgment; reasonable-and-prudent following remains unresolved.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import finalize_report
    finalize_report(args.attempt, args.output)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        print('ValueError: ' + str(error), file=sys.stderr)
        sys.exit(2)
