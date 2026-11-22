"""Independent CPU audit of authored isolation and saved following observables."""
import argparse
import json
from pathlib import Path

from following import measure


OBSERVED = {
    'target_body_gap_m': 'mean_along_route_body_gap_m',
    'ego_target_speed_mps': 'mean_ego_speed_mps',
    'surrounding_vehicle_count': 'mean_surrounding_vehicle_count',
    'precipitation_percent': 'mean_native_precipitation_strength',
}


def audit(plan, comparison_id, reports):
    """Reject missing sources, off-pair reports, or an unobserved difference."""
    if isinstance(plan, (str, Path)):
        plan = json.loads(Path(plan).read_text())
    comparisons = [c for c in plan['comparisons'] if c['comparison_id'] == comparison_id]
    if len(comparisons) != 1:
        raise ValueError('unknown or duplicate comparison')
    pair = comparisons[0]
    cases = {c['case_id']: c for c in plan['cases']}
    if len(pair['case_ids']) != 2 or any(cid not in cases for cid in pair['case_ids']):
        raise ValueError('comparison does not bind two exact cases')
    left, right = (cases[cid] for cid in pair['case_ids'])
    changed = pair['deliberate_differences']
    if len(changed) != 1 or changed[0] not in OBSERVED:
        raise ValueError('unsupported comparison difference')
    changed = changed[0]
    a, b = left['world_setup'], right['world_setup']
    if set(a) != set(b) or {k for k in a if a[k] != b[k]} != {changed}:
        raise ValueError('authored fixed conditions differ outside declared variable')
    if a[changed] == b[changed]:
        raise ValueError('declared variable does not differ')
    if set(reports) != set(pair['case_ids']):
        raise ValueError('missing or extra exact-case measurement report')
    values = []
    for cid in pair['case_ids']:
        report = reports[cid]
        if report.get('case_id') != cid or report.get('format') != 'worker-following-measurements':
            raise ValueError('measurement report has wrong exact case')
        if report.get('legal_reasonableness_verdict') != 'unresolved':
            raise ValueError('measurement report asserts legal outcome')
        if not all(report.get('sources', {}).get(s) for s in ('following-history.jsonl', 'following-context.json')):
            raise ValueError('original measurement sources missing')
        if report.get('steady_window_s') != [14, 20] or report.get('steady_frame_count', 0) < 3:
            raise ValueError('steady following observation missing')
        if not report.get('raw_history') or report.get('lane_change_first_frame') is None:
            raise ValueError('raw history or lane change missing')
        value = report.get(OBSERVED[changed])
        if type(value) not in (int, float):
            raise ValueError('declared observed variable missing')
        values.append(value)
    if abs(values[1]-values[0]) < 1e-3:
        raise ValueError('declared change not observed in original history')
    return {'comparison_id': comparison_id, 'case_ids': pair['case_ids'],
            'declared_difference': changed, 'observed_values': values,
            'legal_reasonableness_verdict': 'unresolved'}


def audit_attempts(plan_path, comparison_id, attempts, *, diagnostic=False):
    """Recompute both reports from sealed Native files before comparison."""
    plan = json.loads(Path(plan_path).read_text())
    pair = next((c for c in plan['comparisons'] if c['comparison_id'] == comparison_id), None)
    if pair is None or set(attempts) != set(pair['case_ids']):
        raise ValueError('attempt paths do not match comparison cases')
    reports = {case_id: measure(path, case_id, diagnostic=diagnostic)
               for case_id, path in attempts.items()}
    return audit(plan, comparison_id, reports)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--attempt', action='append', required=True,
                        help='exact_case_id=original_attempt_directory')
    args = parser.parse_args()
    attempts = {}
    for item in args.attempt:
        case_id, separator, path = item.partition('=')
        if not separator or case_id in attempts:
            raise ValueError('each attempt needs a distinct exact case ID')
        attempts[case_id] = path
    print(json.dumps(audit_attempts(args.plan, args.comparison, attempts), indent=2))


if __name__ == '__main__':
    main()
