"""Independent source-row assessment of requested pedestrian motion.

The software result describes observed footprint entry only. Signal governance,
device permission, visible pixels, and legal outcome require original review.
"""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(attempt, case_id):
    attempt = Path(attempt)
    required = ('config.json', 'red-entry-original.jsonl', 'video_frames.jsonl')
    available = {name: sha(attempt / name) for name in required if (attempt / name).is_file()}
    missing = sorted(set(required) - set(available))
    observed = None
    error = None
    if not missing:
        try:
            config = json.loads((attempt / 'config.json').read_text())
            samples = [json.loads(s) for s in (attempt / required[1]).read_text().splitlines() if s]
            frames = [json.loads(s) for s in (attempt / required[2]).read_text().splitlines() if s]
            if config['case_id'] != case_id or config['frames'] != 600 or len(samples) != 600 or len(frames) != 600:
                raise ValueError('Exact case or 600-frame source window differs')
            if any(row['native_frame'] != mapping['carla_frame'] or
                   abs(row['time_s'] - mapping['time_s']) > 1e-6
                   for row, mapping in zip(samples, frames)):
                raise ValueError('Original frame/time join differs')
            if any(row['traffic']['state'] != 'red' for row in samples):
                raise ValueError('Steady-red source readback differs')
            roadway = config['roadway_y_abs_max_m']
            entered = any(any(abs(point[1]) <= roadway for point in row['footprint_xy_m'])
                          for row in samples)
            observed = entered == config['requested_entry']
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
    status = 'unverified' if observed is None else 'met' if observed else 'not_met'
    method = '600 original pedestrian footprint rows joined by frame/time to camera map and authored roadway corridor'
    result = {'format': 'c111331-physical-outcome-v1', 'case_id': case_id,
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_checks': {'maneuver': {'status': status, 'method': method,
                  'sources': available, 'missing_evidence': missing + ([error] if error else []),
                  'observed_target': observed, 'physical_causation_claimed': False,
                  'legal_verdict_claimed': False}},
              'maneuver_completed': status == 'met',
              'realized_observables': ({'requested_footprint_entry': {
                  'value': observed, 'source': 'red-entry-original.jsonl', 'method': method}}
                  if status == 'met' else {}),
              'original_native_observed': False, 'legal_verdict_claimed': False}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = assess(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['physical_checks']['maneuver']['status']}))
