"""Independently test following completion on synthetic Native-shaped rows.

These checks demonstrate software behavior only. They never claim physical CARLA
motion, public highway status, visibility, or a legal following threshold.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(rows, expected):
    if not rows:
        return 'unverified', None
    frames = [r.get('native_frame') for r in rows]
    times = [r.get('time_s') for r in rows]
    if any(not isinstance(frame, int) for frame in frames):
        return 'unverified', None
    if any(not isinstance(t, (int, float)) for t in times):
        return 'unverified', None
    gaps = []
    for row in rows:
        ego, lead = row.get('ego', {}), row.get('lead', {})
        if (ego.get('native_road_id'), ego.get('native_lane_id')) != (lead.get('native_road_id'), lead.get('native_lane_id')):
            return 'not_met', None
        if min(ego.get('speed_mps', 0), lead.get('speed_mps', 0)) <= 0:
            return 'not_met', None
        try:
            gap = min(point[0] for point in lead['native_body_xy_m']) - max(point[0] for point in ego['native_body_xy_m'])
        except (KeyError, TypeError, ValueError):
            return 'unverified', None
        if gap <= 0:
            return 'not_met', gap
        gaps.append(gap)
    if frames != list(range(frames[0], frames[0] + len(rows))):
        return 'not_met', None
    if len(rows) != expected or times[-1] - times[0] < 44.9:
        return 'not_met', None
    return 'met', sum(gaps)/len(gaps)


def run(case, variant, output):
    if case not in ('condition_a', 'condition_b'):
        raise ValueError('Unknown exact following condition')
    source = ROOT/'current-fixture'/case/'native_samples.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    if variant == 'incomplete_motion':
        rows = rows[:500]
    elif variant == 'missing_evidence':
        rows = []
    elif variant != 'complete_motion':
        raise ValueError('Unknown fixture variant')
    status, gap = classify(rows, 900)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}[variant]
    if status != expected:
        raise ValueError('Synthetic fixture did not produce expected completion status')
    case_id = json.loads((ROOT/'case-plan.json').read_text())['cases'][0 if case == 'condition_a' else 1]['case_id']
    result = {
        'case_id': case_id,
        'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True,
        'maneuver_completed': status == 'met',
        'physical_checks': {'maneuver': {
            'status': status,
            'method': 'independent original-shaped frame, lane, motion, body-gap and full-window join',
            'sources': [{'path':str(source.relative_to(ROOT)),'sha256':digest(source),'selected_rows':len(rows)}],
        }},
        'realized_observables': ({'synthetic_mean_bumper_gap_m':gap} if status == 'met' else {}),
        'physical_acceptance_claimed': False,
        'legal_verdict_claimed': False,
    }
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case':case,'variant':variant,'status':status,'rows':len(rows),'synthetic_only':True}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--variant',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    run(args.case,args.variant,args.output)
