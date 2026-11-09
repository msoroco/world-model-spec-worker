"""Saved-only NRS 484B.407 measurements; leaves legal meaning unresolved."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_turn(root):
    history = rows(source(root, 'turn_history.jsonl'))
    if not history:
        raise ValueError('Empty turn history')
    headings = [r['heading_deg'] for r in history]
    change = sum((b - a + 180) % 360 - 180 for a, b in zip(headings, headings[1:]))
    return {'sampled_heading_change_deg': change,
            'forward_reverse_phases_observed': len({r['requested_reverse'] for r in history}) == 2,
            'first_reverse_frame': next((r['frame'] for r in history if r['requested_reverse']), None),
            'first_frame': history[0]['frame'], 'last_frame': history[-1]['frame']}


def measure_curve(root):
    context = json.loads(source(root, 'curve_context.json').read_text())
    native_map = source(root, 'road.xodr').read_text()
    if 'arc curvature=' not in native_map or '<elevation' not in native_map:
        raise ValueError('Native map lacks curve and crest profile')
    return {'authored_curve_radius_m': context['curve_radius_m'],
            'native_map_sha256': sha(root / 'road.xodr'),
            'turn_station_m': context['turn_station_m'],
            'native_surface_review_pending': True}


def measure_visibility(root):
    history = rows(source(root, 'visibility_history.jsonl'))
    if not history:
        raise ValueError('Empty visibility history')
    samples = []
    for row in history:
        value = row['visibility']
        if value.get('probe_distance_m') != 152.4:
            raise ValueError('500-foot source probe missing')
        approaches = value.get('approaches', [])
        if len(approaches) != 2:
            raise ValueError('Both incoming directions required')
        samples.append({'frame': row['frame'], 'approaches': [
            {'lane_id': a['lane_id'], 'any_sample_clear_at_probe': a.get('any_sample_clear_at_probe'),
             'any_body_sight_horizon': a.get('any_body_sight_horizon'),
             'body_rays_at_probe': a.get('body_rays_at_probe'),
             'unknown_reason': a.get('unknown_reason')} for a in approaches]})
    return {'distance_m': 152.4, 'distance_kind': 'incoming lane waypoint arc length',
            'observer': 'virtual eye 1.4 m above both incoming Native lanes',
            'target': 'actual subject center and eight body corners per sampled frame',
            'samples': samples, 'not_driver_perception': True,
            'legal_visibility_standard': 'unresolved'}


def measure_approach(root):
    history = rows(source(root, 'approach_history.jsonl'))
    if len(history) < 2 or len({r['frame'] for r in history}) != len(history):
        raise ValueError('Approaching vehicle history incomplete')
    return {'lane_ids': sorted({r['lane_id'] for r in history}),
            'first_station_m': history[0]['station_m'],
            'last_station_m': history[-1]['station_m'],
            'native_body_history_frames': len(history),
            'moving_toward_turn_site': history[-1]['station_m'] < history[0]['station_m']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.attempt
    config = json.loads(source(root, 'config.json').read_text())
    measurements = {}
    specs = [('turn', measure_turn, ['turn_history.jsonl']),
             ('curve', measure_curve, ['curve_context.json', 'road.xodr']),
             ('visibility_500ft', measure_visibility, ['visibility_history.jsonl']),
             ('approaching_vehicle', measure_approach, ['approach_history.jsonl'])]
    for key, method, inputs in specs:
        measurements[key] = {'method': method.__name__, 'value': method(root),
                             'sources': {name: sha(source(root, name)) for name in inputs}}
    from worker_exchange.native_output import physical_result, write_result, finalize_report
    turn = measurements['turn']['value']
    visibility = measurements['visibility_500ft']['value']
    # This comparison is an observed raw ray category, never a legal label.
    frames = visibility['samples']
    maneuver_frame = turn['first_reverse_frame']
    selected = next((f for f in frames if f['frame'] == maneuver_frame), None)
    clear = [a['any_sample_clear_at_probe'] for a in selected['approaches']] if selected else []
    observed = 'unknown' if len(clear) != 2 or any(v is None for v in clear) else ('visible_both' if all(clear) else 'occluded_one_or_both')
    requested = config['visibility_variant']
    target_check = {'target': 'sampled_500ft_rays_during_turn', 'requested': requested,
                    'measured': observed, 'method': 'actual subject nine-body 152.4m source rays',
                    'tolerance': 'raw category only; no legal threshold',
                    'matched': observed == requested, 'physical_cause_confirmed': False,
                    'cause_evidence': 'visibility_history.jsonl; rendered mountain occlusion requires Native review'}
    result = {'case_id': config['selected_case_id'], 'measured_values': measurements,
              'target_checks': [target_check], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Saved evidence assessment pending',
              'physical_failure_flags': {'collision_unreviewed': True},
              'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': [{'source': 'visibility_history.jsonl',
                                     'sha256': sha(root / 'visibility_history.jsonl')},
                                    {'source': 'approach_history.jsonl',
                                     'sha256': sha(root / 'approach_history.jsonl')}],
              'realized_observables': {}, 'legal_judgment': 'unresolved'}
    # Keep legal judgment outside result schema fields consumed by adapters.
    result.pop('legal_judgment')
    result = physical_result(root, result)
    write_result(root, result)
    args.output.write_text(json.dumps({'format': 'worker-analysis-report',
        'case_id': config['selected_case_id'], 'measurements': measurements,
        'raw_visibility_category': observed, 'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'unresolved_judgment_calls': ['meaning of seen by driver',
                                      'meaning of on curve/near crest',
                                      'actual-traffic necessity'],
        'analysis_complete': True}, indent=2) + '\n')
    finalize_report(root, args.output)


if __name__ == '__main__':
    main()
