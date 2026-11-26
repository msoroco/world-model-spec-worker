"""Independent saved-source comparison for the two exact flagger probes.

This checks original-source identity and measured event order. A requested
signal is not proof of an authorized, visible signal or a legal conclusion.
"""

import argparse
import json
from pathlib import Path

from check_requests import check_pair, read_case
from measure_original import measure, sha


def audit(first_attempt, second_attempt, base=None):
    base = Path(base) if base is not None else Path(__file__).resolve().parent
    check_pair(base=base)
    a_config, _ = read_case('probe_a', base=base)
    b_config, _ = read_case('probe_b', base=base)
    attempts = (Path(first_attempt), Path(second_attempt))
    results = [measure(path, config['case_id']) for path, config in
               zip(attempts, (a_config, b_config))]
    fixed_sources = ('road.xodr', 'original-flagger-review.json')
    for name in fixed_sources:
        if sha(attempts[0] / name) != sha(attempts[1] / name):
            raise ValueError('Paired original fixed source differs: ' + name)
    for name in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                 'frame_count', 'stop_line_x_m', 'requested_route',
                 'signal_policy', 'cameras', 'assignment_sha256'):
        if a_config[name] != b_config[name]:
            raise ValueError('Paired construction fixed condition differs: ' + name)
    if a_config['controller_policy'] == b_config['controller_policy']:
        raise ValueError('Paired response controller difference absent')
    return {
        'format': 'c183370-original-comparison-audit',
        'case_ids': [a_config['case_id'], b_config['case_id']],
        'source_seal_sha256': [row['source_seal_sha256'] for row in results],
        'fixed_original_source_sha256': {name: sha(attempts[0] / name)
                                         for name in fixed_sources},
        'deliberate_difference': 'requested_motorcycle_response_to_fixed_flagger_signal',
        'observed_cross_frames': [row['first_observed_stop_line_cross_frame']
                                  for row in results],
        'observed_body_cross_frames': [
            row['first_observed_body_stop_line_cross_frame'] for row in results],
        'stopped_frames_during_requested_stop': [
            row['observed_stopped_frames_during_requested_stop'] for row in results],
        'body_crossed_during_requested_stop': [
            row['body_crossed_during_requested_stop'] for row in results],
        'requested_indications_at_crossing': [
            row['requested_indication_at_crossing'] for row in results],
        'observed_response_difference':
            results[0]['first_observed_stop_line_cross_frame'] !=
            results[1]['first_observed_stop_line_cross_frame'],
        'original_signal_pixels_reviewed': False,
        'flagger_authority_verified': False,
        'zone_designation_verified': False,
        'physical_completion': None,
        'legal_verdict': None,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe-a', required=True)
    parser.add_argument('--probe-b', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = audit(args.probe_a, args.probe_b)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
