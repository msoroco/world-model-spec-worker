"""Saved-only truck-gap measurements from original frame-joined Native sources."""
import argparse
import hashlib
import json
from pathlib import Path

from truck_measurements import analyze


CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
GAP_TARGETS_M = {'gap_below_500ft': 150.0, 'gap_at_500ft': 152.4,
                 'gap_above_500ft': 155.0}
WIDTH_CASES = {'ego_width_below_80in': ('ego','below'),
               'ego_width_at_80in': ('ego','at'),
               'lead_width_below_80in': ('lead','below')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_minimum_truck_body_gap(report):
    """Minimum sampled longitudinal surface gap, in metres."""
    return min(sample['longitudinal_body_gap_m'] for sample in report['samples'])


def measure_truck_widths(report):
    """Smallest original overall width for each observed vehicle, in metres."""
    return {role: min(sample[role]['width_m'] for sample in report['samples'])
            for role in ('ego', 'lead')}


def measure_lane_count(report):
    return report['native_road_context']['same_direction_lane_count']


def finalize(attempt: Path, output: Path):
    from worker_exchange.native_output import physical_result, write_result
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior truck finalization; choose a fresh attempt')
    required = ('config.json', 'road_context.json', 'truck_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl', *CAMERAS)
    for name in required:
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt/'config.json').read_text())
    case = config.get('selected_case_id', '')
    suffix = case.removeprefix('testing__C149237__NRS-484B-127-2__heavy_vehicle_driver__')
    if suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES:
        raise ValueError('Wrong exact truck case')
    report = analyze(attempt)
    samples = report['samples']
    if not samples:
        raise ValueError('Missing source-bound truck following interval')
    minimum = measure_minimum_truck_body_gap(report)
    widths = measure_truck_widths(report)
    channels = attempt/'channels'
    if channels.exists():
        raise ValueError('Retain prior derived truck channels')
    channels.mkdir()
    values = {
        'longitudinal_body_gap': [s['longitudinal_body_gap_m'] for s in samples],
        'ego_overall_width': [s['ego']['width_m'] for s in samples],
        'lead_overall_width': [s['lead']['width_m'] for s in samples],
        'same_direction_lane_count': [report['native_road_context']['same_direction_lane_count'] for _ in samples],
    }
    for name, numbers in values.items():
        with (channels/(name+'.jsonl')).open('x') as stream:
            for sample, number in zip(samples, numbers):
                stream.write(json.dumps({'original_frame': sample['frame'],
                                         'time_s': sample['time_s'], 'value': number},
                                        allow_nan=False)+'\n')
    (channels/'conditions_permitting.json').write_text(json.dumps({
        'conditions_permitting': {
            'judgment': 'unresolved',
            'road_context_reference': 'road_context.json',
            'original_observations_reference': 'capture/evidence.jsonl',
            'traffic_and_visibility_require_source_review': True}},
        indent=2)+'\n')
    evidence = [{'name': name, 'unit': ('count' if name == 'same_direction_lane_count' else 'm'),
                 'reference': 'channels/'+name+'.jsonl'} for name in values]
    evidence.append({'name': 'conditions_permitting', 'unit': 'source review',
                     'reference': 'channels/conditions_permitting.json'})
    if suffix in GAP_TARGETS_M:
        target_check = {'target': 'minimum_sampled_body_gap_m',
                        'requested': GAP_TARGETS_M[suffix], 'measured': minimum,
                        'method': 'original body vertices projected on sourced lane tangent',
                        'tolerance': 2.0,
                        'matched': abs(minimum-GAP_TARGETS_M[suffix]) <= 2.0,
                        'physical_cause_confirmed': False,
                        'cause_evidence': ['truck_history.jsonl','video_frames.jsonl']}
    else:
        role, category = WIDTH_CASES[suffix]
        threshold = 80 * .0254
        value = widths[role]
        requested = 2.0 if category=='below' else threshold
        target_check = {'target': role+'_minimum_overall_width_m',
                        'requested': requested, 'measured': value,
                        'method': 'minimum original Native overall body width for '+role,
                        'tolerance': .005,
                        'matched': abs(value-requested) <= .005,
                        'physical_cause_confirmed': False,
                        'cause_evidence': ['truck_history.jsonl','video_frames.jsonl']}
    result = {'case_id': case,
              'measured_values': {'minimum_sampled_body_gap_m': minimum,
                                  'minimum_overall_width_m': widths,
                                  'same_direction_lane_count': report['native_road_context']['same_direction_lane_count']},
              'target_checks': [target_check],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved truck source analysis; independent physical audit pending',
              'physical_failure_flags': ['actual following interval and truck class require source review',
                                         'conditions permitting and safe overtaker occupancy unresolved'],
              'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'source_evidence_hashes': report['sources'],
              'capture_evidence_sha256': sha(attempt/'capture/evidence.jsonl'),
              'realized_observables': {}}
    result = physical_result(attempt, result)
    analysis = {'format': 'worker-truck-gap-analysis', 'case_id': case,
                'measurements': {
                    'minimum_sampled_body_gap_m': {'value': minimum,
                                                   'method': 'measure_minimum_truck_body_gap',
                                                   'sources': report['sources']},
                    'minimum_overall_width_m': {'value': widths,
                                                'method': 'measure_truck_widths',
                                                'sources': report['sources']},
                    'same_direction_lane_count': {'value': report['native_road_context']['same_direction_lane_count'],
                                                  'method': 'measure_lane_count',
                                                  'sources': report['sources']}},
                'legal_conclusion': 'unresolved', 'source_report': report}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+'\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(Path(args.attempt),Path(args.output))


if __name__ == '__main__':
    main()
