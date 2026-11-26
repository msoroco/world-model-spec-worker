"""Source-bound pairwise audit for the four selected lamp comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_audit import audit_saved
from source_packet import ASSIGNMENT, verify


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def audit(comparison_id, left, right):
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / 'case-plan.json').read_text())
    comparison = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison_id), None)
    if comparison is None or len(comparison['case_ids']) != 2:
        raise ValueError('unknown exact lamp comparison')
    left_key, right_key = [case.removeprefix(ASSIGNMENT + '__') for case in comparison['case_ids']]
    if Path(left).resolve() == Path(right).resolve():
        raise ValueError('comparison needs distinct cases')
    left_audit = audit_saved(left, left_key)
    right_audit = audit_saved(right, right_key)
    left_scene = verify(Path(left) / 'lamp-context-packet.json', left_key)['packet']['scene']
    right_scene = verify(Path(right) / 'lamp-context-packet.json', right_key)['packet']['scene']
    fixed = ('cell_id', 'actor', 'nevada_jurisdiction', 'public_highway', 'highway',
             'vehicle_class', 'parked', 'parking_status', 'required_lamp_ids',
             'required_lamp_provisions', 'map_sha256', 'route_xy', 'route')
    if any(left_scene.get(name) != right_scene.get(name) for name in fixed):
        raise ValueError('comparison changed fixed highway, vehicle or route source')
    if comparison_id == 'device_lamps_on_off':
        if not (left_scene['device_directs'] and right_scene['device_directs'] and
                left_scene['lamps_on_request'] and not right_scene['lamps_on_request'] and
                left_scene['clock_time_s'] == right_scene['clock_time_s'] and
                left_scene['visibility_ahead_m'] == right_scene['visibility_ahead_m']):
            raise ValueError('lamp state comparison variable changed')
    elif comparison_id == 'device_vs_no_device':
        if not (left_scene['device_directs'] and not right_scene['device_directs'] and
                not left_scene['lamps_on_request'] and not right_scene['lamps_on_request'] and
                left_scene['clock_time_s'] == right_scene['clock_time_s'] and
                left_scene['visibility_ahead_m'] == right_scene['visibility_ahead_m']):
            raise ValueError('official device comparison variable changed')
    elif comparison_id == 'day_vs_night':
        if not (left_scene['device_directs'] and right_scene['device_directs'] and
                left_scene['lamps_on_request'] and right_scene['lamps_on_request'] and
                left_scene['clock_time_s'] != right_scene['clock_time_s'] and
                left_scene['visibility_ahead_m'] == right_scene['visibility_ahead_m']):
            raise ValueError('clock context comparison variable changed')
    elif comparison_id == 'day_vs_poor_visibility':
        if not (left_scene['device_directs'] and right_scene['device_directs'] and
                left_scene['lamps_on_request'] and right_scene['lamps_on_request'] and
                left_scene['clock_time_s'] == right_scene['clock_time_s'] and
                left_scene['visibility_ahead_m'] >= 304.8 > right_scene['visibility_ahead_m']):
            raise ValueError('1000-foot visibility context comparison variable changed')
    else:
        raise ValueError('unreviewed comparison')
    left_rows = rows(Path(left) / 'original-lamp-ticks.jsonl')
    right_rows = rows(Path(right) / 'original-lamp-ticks.jsonl')
    if (len(left_rows) != 900 or len(right_rows) != 900 or
            any(a['original_frame'] != b['original_frame'] or a['time_s'] != b['time_s']
                for a, b in zip(left_rows, right_rows))):
        raise ValueError('comparison original time/frame grid differs')
    return {'format': 'lamp-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': comparison['case_ids'], 'original_frames': 900,
            'source_packet_sha256': [left_audit['source_packet_sha256'],
                                     right_audit['source_packet_sha256']],
            'passed': True, 'physical_acceptance_claimed': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    for name in ('comparison', 'left', 'right'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right)))


if __name__ == '__main__':
    main()
