"""Independently remeasure fixed-source parked-light contrasts."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_acceptance import audit as delivery_audit
from source_packet import ASSIGNMENT

AXES = {'lamp_dimming': 'lamp_mode', 'cowl_use': 'auxiliary_lamp',
        'parking_lamp_use': 'auxiliary_lamp', 'nighttime': 'night',
        'lawful_parking': 'lawful_park'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison, comparison_id, plan, attempts):
    plan = Path(plan)
    data = json.loads(plan.read_text())
    row = next((item for item in data['comparisons']
                if item['comparison_id'] == comparison), None)
    if (row is None or comparison not in AXES or
            comparison_id != ASSIGNMENT + '__' + comparison or
            len(row.get('case_ids', [])) != 2 or len(attempts) != 2):
        raise ValueError('exact parked-light comparison identity differs')
    scenes, ticks, receipts = [], [], []
    for case_id, attempt in zip(row['case_ids'], attempts):
        attempt = Path(attempt)
        receipts.append(delivery_audit(case_id, attempt, plan))
        packet = ('reviewed-packet.json' if
                  (attempt / 'fixture-provenance.json').is_file() else
                  'source-packet.json')
        scenes.append(json.loads((attempt / packet).read_text())['scene'])
        ticks.append([json.loads(line) for line in
                      (attempt / 'original-ticks.jsonl').read_text().splitlines()])
    left, right = scenes
    axis = AXES[comparison]
    if left[axis] == right[axis]:
        raise ValueError('declared parked-light comparison axis did not change')
    fixed = set(left) - set(AXES.values())
    if set(left) != set(right) or any(left[name] != right[name] for name in fixed):
        raise ValueError('comparison changed fixed parked-light scene/source')
    if any(left[name] != right[name] for name in set(AXES.values()) - {axis}):
        raise ValueError('comparison changed more than one parked-light axis')
    if (len(ticks[0]) != len(ticks[1]) or
            any(a['original_frame'] != b['original_frame'] or
                a['time_s'] != b['time_s'] for a, b in zip(*ticks))):
        raise ValueError('comparison original frame/time alignment differs')
    if comparison == 'lamp_dimming' and not any(
            a['beam_aim_deg'] != b['beam_aim_deg'] for a, b in zip(*ticks)):
        raise ValueError('lamp beam aim contrast was not measured')
    return {'format': 'c229398-independent-comparison-v1',
            'assignment_id': ASSIGNMENT, 'comparison_id': comparison,
            'case_ids': row['case_ids'], 'axis': axis,
            'plan_sha256': sha(plan),
            'delivery_receipt_sha256': [hashlib.sha256(
                json.dumps(item, sort_keys=True).encode()).hexdigest()
                for item in receipts],
            'diagnostic_fixture': all(item['diagnostic_fixture'] for item in receipts),
            'fixed_scene_and_source_hashes': True,
            'original_frame_time_aligned': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--attempt', action='append', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior comparison; choose a fresh output')
    receipt = audit(args.comparison, args.comparison_id,
                    args.plan, args.attempt)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(receipt['comparison_id'])
