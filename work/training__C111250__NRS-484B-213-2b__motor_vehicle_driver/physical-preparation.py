"""Assess source-shaped intersection traversal without making a legal claim."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(source, context, case_id, output):
    source, context, output = Path(source), Path(context), Path(output)
    rows = [json.loads(line) for line in source.read_text().splitlines()] if source.is_file() else []
    region = json.loads(context.read_text())['intersection_x_m'] if context.is_file() else None
    valid = [(row['native_frame'], row['time_s'], min(p[0] for p in row['body_xy_m']),
              max(p[0] for p in row['body_xy_m'])) for row in rows
             if len(row.get('body_xy_m', [])) == 4 and 'native_frame' in row and 'time_s' in row]
    complete = (len(valid) == 600 and [row[0] for row in valid] == list(range(600))
                and all(abs(row[1] - row[0] / 20) < 1e-6 for row in valid)
                and region is not None and valid[0][3] < region[0] - 30.48
                and valid[-1][2] > region[1]
                and all(a[2] <= b[2] for a, b in zip(valid, valid[1:])))
    status = 'unverified' if not source.is_file() or not context.is_file() else ('met' if complete else 'not_met')
    sources = {path.name: sha(path) for path in (source, context) if path.is_file()}
    if not sources:
        sources = {'missing': source.name}
    check = {'status': status,
             'method': 'Joined 600 source-shaped full-body footprints cross the authored intersection at 20 Hz; engineering completion only',
             'sources': sources, 'observed_frames': len(valid),
             'authored_region_x_m': region, 'original_native_observed': False,
             'physical_highway_verified': False}
    result = {'case_id': case_id, 'physical_checks': {'maneuver': check},
              'maneuver_completed': status == 'met',
              'realized_observables': {'intersection_traversed': True} if status == 'met' else {},
              'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'status': status, 'frames': len(valid)}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--context', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assess(args.source, args.context, args.case, args.output)


if __name__ == '__main__':
    main()
