"""Independent source and numeric displacement audit for yield sweep points."""

import json
from math import hypot, isclose
from pathlib import Path

from delivery_audit import audit_attempt, digest


def audit(attempt, report):
    root = Path(attempt)
    result = audit_attempt(root, report)
    if '__yield_release_delay-' not in result['case_id']:
        raise ValueError('Wrong exact yield sweep case')
    bodies = [json.loads(line) for line in
              (root / 'intersection_participants.jsonl').read_text().splitlines() if line.strip()]
    stream_path = root / 'subject_displacement_m.jsonl'
    if not stream_path.is_file():
        raise ValueError('Missing derived original-body displacement stream')
    stream = [json.loads(line) for line in stream_path.read_text().splitlines() if line.strip()]
    if not bodies or len(stream) != len(bodies):
        raise ValueError('Subject displacement stream length differs')
    first = [sum(point[i] for point in bodies[0]['subject_corners']) / 4 for i in (0, 1)]
    for row, sample in zip(bodies, stream):
        center = [sum(point[i] for point in row['subject_corners']) / 4 for i in (0, 1)]
        expected = hypot(*(center[i] - first[i] for i in (0, 1)))
        if sample.get('time_s') != row['time_s'] or not isclose(sample.get('value', float('nan')),
                                                             expected, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError('Subject displacement differs from original body source')
    result['displacement_stream_sha256'] = digest(stream_path)
    result['displacement_recomputed'] = True
    entry_path = root / 'subject_entry_elapsed_s.jsonl'
    if not entry_path.is_file():
        raise ValueError('Missing derived original-body entry timing stream')
    entries = [json.loads(line) for line in entry_path.read_text().splitlines() if line.strip()]
    observations = json.loads(Path(report).read_text())['measurements']['intersection_observation']['value']['observations']
    if len(entries) != len(observations):
        raise ValueError('Subject entry timing stream length differs')
    latched = 0.0
    for observed, sample in zip(observations, entries):
        if latched == 0.0 and observed['subject_in_conflict']:
            latched = observed['time_s']
        if sample.get('time_s') != observed['time_s'] or sample.get('value') != latched:
            raise ValueError('Subject entry timing differs from original body source')
    result['entry_timing_stream_sha256'] = digest(entry_path)
    result['entry_timing_recomputed'] = True
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.report)
    if result['case_id'] != args.case:
        raise ValueError('Wrong exact yield sweep audit argument')
    print(json.dumps({'case_id': args.case,
                      'frame_count': result['frame_count'],
                      'camera_sources': sorted(result['camera_decodes']),
                      'displacement_recomputed': True,
                      'entry_timing_recomputed': True,
                      'physical_visibility_claimed': False}))


if __name__ == '__main__':
    main()
