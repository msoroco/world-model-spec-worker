"""Saved-only rail geometry finalizer; never infers a legal exception or verdict."""

import argparse
import json
from pathlib import Path

from rail_footprint_meter import measure
from rail_source_contract import CAMERAS, load_original, sha


def original_native_source_contract(packet, measured):
    """Return measured rail/vehicle facts, retaining diagnostic provenance."""
    rested = [row for row in measured['frames'] if row['at_rest']]
    band = [row for row in rested if row['inside_50ft_band']]
    final_hold = measured['frames'][-100:]
    sustained_rest = all(row['at_rest'] for row in final_hold)
    return {'frame_count': len(measured['frames']),
            'rested_frame_count': len(rested),
            'rested_inside_50ft_frame_count': len(band),
            'nearest_observed_footprint_gap_m': min(
                row['footprint_to_nearest_rail_m'] for row in measured['frames']),
            'final_five_second_rest_observed': sustained_rest,
            'final_hold_nearest_footprint_gap_m': min(
                (row['footprint_to_nearest_rail_m'] for row in final_hold),
                default=None) if sustained_rest else None,
            'statutory_50ft_m': 15.24,
            'diagnostic_fixture': packet['diagnostic_fixture'],
            'original_native_observed': packet['original_native_observed'],
            'rail_geometry_source_sha256': packet['original_rail_survey_sha256'],
            'source_seal_sha256': packet['original_source_seal_sha256'],
            'rail_identity_reviewed': False,
            'original_pixels_reviewed': False,
            'legal_exception_reviewed': False,
            'legal_verdict': None}


def run(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Fresh saved-only rail analysis required')
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['case_id']
    packet = load_original(attempt, case_id)
    measured = measure(packet)
    summary = original_native_source_contract(packet, measured)
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    values = [{'time_s': row['sim_time_s'], 'value': row} for row in measured['frames']]
    (channels / 'rail-footprint.jsonl').write_text(
        ''.join(json.dumps(row, allow_nan=False) + '\n' for row in values))
    from worker_exchange.native_output import physical_result, write_result
    observed_gap = summary['final_hold_nearest_footprint_gap_m']
    if observed_gap is None:
        observed_gap = summary['nearest_observed_footprint_gap_m']
    result = {'case_id': case_id, 'measured_values': summary,
              'target_checks': [{'target': 'observed curbside body distance to nearest physical rail',
                                 'requested': config['target_footprint_gap_m'],
                                 'measured': observed_gap,
                                 'method': 'sealed original Native pose/extent and both surveyed rail polylines',
                                 'tolerance': 0.75,
                                 'matched': abs(observed_gap - config['target_footprint_gap_m']) <= 0.75,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['original-rail-survey.json', 'original-native-rows.jsonl']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original sources measured; rail identity, pixel meaning and legal exceptions unreviewed',
              'physical_failure_flags': ['original_rail_identity_and_context_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS] + ['raw.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [{'name': 'rail_footprint', 'unit': 'm',
                                      'reference': 'channels/rail-footprint.jsonl'}],
              'realized_observables': {}, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    write_result(attempt, physical_result(attempt, result))
    sources = {name: sha(attempt / name) for name in
               ('original-rail-survey.json', 'original-native-rows.jsonl',
                'video_frames.jsonl', 'capture-seal.json')}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {
                  'parking_event_source': {'value': summary,
                      'method': 'original_native_source_contract', 'sources': sources},
                  'nearest_rail_gap': {'value': summary,
                      'method': 'original_native_source_contract', 'sources': sources},
                  'rail_footprint': {'value': summary,
                      'method': 'original_native_source_contract', 'sources': sources}},
              'source_complete': True,
              'diagnostic_fixture': packet['diagnostic_fixture'],
              'original_native_observed': packet['original_native_observed'],
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.attempt, args.output), sort_keys=True))
