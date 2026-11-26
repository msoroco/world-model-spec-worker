"""Reopen released original sources and independently audit one frozen contrast."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from comparison_audit import audit_pair
from delivery_audit import audit as audit_delivery, linked
from native_measurement import measure
from reviewed_site import verify

HERE = Path(__file__).resolve().parent
MOTIONS = {'posted_enter': 'enter_roadway', 'posted_stop': 'stop_before_roadway',
           'posted_remain_trail': 'remain_trail'}


def measure_released(root: Path, receipt_path: Path) -> tuple[dict, dict]:
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    delivery = audit_delivery(root, receipt)
    case_id = receipt['case_id']
    suffix = case_id.removeprefix(HERE.name + '__')
    if case_id != HERE.name + '__' + suffix or suffix not in MOTIONS:
        raise ValueError('exact original comparison case required')
    site = verify(linked(root, receipt['site_ref']))['site']
    packet = json.loads(linked(root, receipt['capture_packet_ref']).read_text(encoding='utf-8'))
    measurement = measure(site, packet, {'case_id': case_id, 'motion': MOTIONS[suffix]})
    if delivery['roadway_frames'] != measurement['roadway_frames']:
        raise ValueError('delivery and comparison roadway measurements differ')
    return measurement, delivery


def main() -> None:
    parser = argparse.ArgumentParser()
    for side in ('left', 'right'):
        parser.add_argument('--' + side + '-root', type=Path, required=True)
        parser.add_argument('--' + side + '-receipt', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    roots = [args.left_root.resolve(), args.right_root.resolve()]
    output = args.output.resolve()
    if output.exists() or any(output.is_relative_to(root) for root in roots):
        raise ValueError('fresh comparison receipt outside source roots required')
    left, left_delivery = measure_released(roots[0], args.left_receipt)
    right, right_delivery = measure_released(roots[1], args.right_receipt)
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    result = audit_pair(plan, left, right, args.comparison)
    result['delivery_audits'] = [left_delivery, right_delivery]
    result['physical_completion_confirmed'] = False
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
