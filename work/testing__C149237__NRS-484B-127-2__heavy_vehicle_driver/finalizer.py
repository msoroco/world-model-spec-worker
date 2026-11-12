"""Saved-only truck-gap measurements from original frame-joined Native sources."""
import argparse
import hashlib
import json
from pathlib import Path

from truck_measurements import analyze


CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    if not case.endswith('__gap_below_500ft'):
        raise ValueError('Wrong exact qualifying truck case')
    report = analyze(attempt)
    samples = report['samples']
    if not samples:
        raise ValueError('Missing source-bound truck following interval')
    minimum = min(sample['longitudinal_body_gap_m'] for sample in samples)
    widths = {'ego': min(sample['ego']['width_m'] for sample in samples),
              'lead': min(sample['lead']['width_m'] for sample in samples)}
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
    evidence = [{'name': name, 'unit': ('count' if name == 'same_direction_lane_count' else 'm'),
                 'reference': 'channels/'+name+'.jsonl'} for name in values]
    target = 150.0
    result = {'case_id': case,
              'measured_values': {'minimum_sampled_body_gap_m': minimum,
                                  'minimum_overall_width_m': widths,
                                  'same_direction_lane_count': report['native_road_context']['same_direction_lane_count']},
              'target_checks': [{'target': 'minimum_sampled_body_gap_m', 'requested': target,
                                 'measured': minimum,
                                 'method': 'original body vertices projected on sourced lane tangent',
                                 'tolerance': 2.0, 'matched': abs(minimum-target) <= 2.0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['truck_history.jsonl', 'video_frames.jsonl']}],
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
