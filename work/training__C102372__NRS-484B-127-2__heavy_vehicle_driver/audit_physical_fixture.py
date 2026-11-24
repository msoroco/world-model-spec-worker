"""Independently classify selected synthetic truck motion and lifecycle order."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUFFIXES = ('probe_1', 'probe_2', 'two_lane_exception', 'passing_hold',
            'passing_overtake', 'conditions_steady', 'conditions_lead_brake')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def center(vertices: list) -> tuple[float, float]:
    assert len(vertices) == 8
    return tuple((min(p[i] for p in vertices) + max(p[i] for p in vertices)) / 2
                 for i in (0, 1))


def run(case: str, variant: str, output: Path) -> None:
    if case not in SUFFIXES:
        raise ValueError('Unknown selected truck case')
    path = HERE / 'selected-fixture' / case / 'truck_history.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Original fixture lacks 600 motion rows')
    if variant == 'incomplete_motion':
        rows = rows[:10]
    elif variant == 'missing_evidence':
        rows = []
    elif variant != 'complete_motion':
        raise ValueError('Unknown physical fixture variant')
    status = 'unverified'
    distance = None
    if rows:
        if any(row.get('frame') != rows[0]['frame'] + i or
               not math.isclose(row.get('time_s', -1), i / 20, abs_tol=1e-6)
               for i, row in enumerate(rows)):
            status = 'unverified'
        else:
            ego = [center(row['ego_vertices_m']) for row in rows]
            lead = [center(row['lead_vertices_m']) for row in rows]
            distance = sum(math.dist(a, b) for a, b in zip(ego, ego[1:]))
            if case == 'passing_overtake':
                motion_met = lead[0][0] > ego[0][0] and lead[-1][0] < ego[-1][0] and (
                    max(p[1] for p in ego) - min(p[1] for p in ego) >= 1)
            else:
                motion_met = distance >= 0.25 and all(b[0] > a[0] for a, b in zip(ego, lead))
            status = 'met' if len(rows) == 600 and motion_met else 'not_met'
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[variant]
    if status != expected:
        raise ValueError('Source-bound physical status differs: ' + status)
    result = {
        'format': 'c102372-physical-fixture-result-v1',
        'case_id': HERE.name + '__' + case, 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'maneuver_completed': status == 'met',
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'independent original-frame body-center, lead order, lateral transition and full-window assessment',
            'sources': [{'path': str(path.relative_to(HERE)), 'sha256': digest(path),
                         'selected_rows': len(rows)}]}},
        'realized_observables': ({'sampled_body_center_path_m': distance}
                                 if status == 'met' else {}),
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case': case, 'variant': variant, 'status': status,
                      'source_sha256': digest(path), 'synthetic_only': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--variant', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.variant, args.output)
