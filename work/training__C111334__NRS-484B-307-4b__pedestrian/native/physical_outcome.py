"""Assess a source-row pedestrian crossing request, without legal inference."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(attempt, case_id):
    attempt = Path(attempt)
    required = ('config.json', 'c111334-native-samples.jsonl', 'video_frames.jsonl')
    sources = {name: sha(attempt / name) for name in required
               if (attempt / name).is_file()}
    missing = sorted(set(required) - set(sources))
    observed = None
    error = None
    if not missing:
        try:
            config = json.loads((attempt / 'config.json').read_text())
            native = [json.loads(s) for s in (attempt / required[1]).read_text().splitlines() if s]
            mapping = [json.loads(s) for s in (attempt / required[2]).read_text().splitlines() if s]
            if (config['case_id'] != case_id or len(native) != 600 or
                    len(mapping) != 600 or config['duration_s'] != 30 or
                    config['rate_hz'] != 20):
                raise ValueError('Exact case or 600-frame source window differs')
            if any(row['native_frame'] != frame['carla_frame'] or
                   row['video_frame'] != frame['video_frame'] or
                   abs(row['time_s'] - frame['time_s']) > 1e-4
                   for row, frame in zip(native, mapping)):
                raise ValueError('Native and source-camera frame join differs')
            entered = any(min(p[1] for p in row['pedestrian_body_polygon_xy_m']) <= 3 and
                          max(p[1] for p in row['pedestrian_body_polygon_xy_m']) >= -3
                          for row in native)
            observed = entered == (config['case_suffix'] != 'probe_1')
        except (ValueError, KeyError, TypeError) as exc:
            error = str(exc)
    status = 'unverified' if observed is None else 'met' if observed else 'not_met'
    method = ('600 original pedestrian body-footprint rows joined by Native '
              'frame/time to four-camera map and authored highway corridor')
    return {
        'format': 'c111334-physical-outcome-v1', 'case_id': case_id,
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'physical_checks': {'maneuver': {'status': status, 'method': method,
            'sources': sources, 'missing_evidence': missing + ([error] if error else []),
            'observed_target': observed, 'physical_causation_claimed': False,
            'legal_verdict_claimed': False}},
        'maneuver_completed': status == 'met',
        'realized_observables': ({'requested_highway_entry': {
            'value': observed, 'source': required[1], 'method': method}}
            if status == 'met' else {}),
        'original_native_observed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = assess(args.attempt, args.case)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['physical_checks']['maneuver']['status']}))
