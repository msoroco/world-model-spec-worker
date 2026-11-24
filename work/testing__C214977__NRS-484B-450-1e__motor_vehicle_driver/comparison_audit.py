"""Independent, source-bound audit of the seven planned crosswalk comparisons.

Inputs are local review receipts, never worker fixture outcomes. A comparison is
complete only after both exact cases have separately passed delivery review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


class ComparisonError(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ComparisonError(message)


def sealed(root: Path, ref: dict) -> dict:
    need(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'sealed receipt reference required')
    root = root.resolve()
    path = (root / ref['path']).resolve()
    need(path.is_relative_to(root) and path.is_file(), 'receipt outside root or absent')
    raw = path.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'receipt hash mismatch')
    return json.loads(raw)


def _case(root: Path, ref: dict, case_id: str) -> dict:
    need(isinstance(ref, dict) and set(ref) == {'delivery','source'},
         'delivery and comparison source references required')
    delivery = sealed(root, ref['delivery'])
    need(delivery.get('format') == 'worker-delivery-audit' and
         delivery.get('case_id') == case_id, 'exact delivery receipt mismatch')
    checks = delivery.get('checks',{})
    need(delivery.get('passed') is True and
         all(checks.get(name) is True for name in ('native_source','all_participants',
              'time_join','full_video_decode','actual_pixels','physical_completion')),
         'delivery acceptance or physical proof missing')
    source = sealed(root, ref['source'])
    need(source.get('format') == 'crosswalk-comparison-source' and
         source.get('case_id') == case_id, 'comparison source mismatch')
    need(source.get('source_receipt_sha256') == delivery.get('native_receipt_sha256'),
         'comparison source differs from reviewed Native receipt')
    need(source.get('original_frame_count') == 900 and
         source.get('source_format') == 'native_original', 'original source profile missing')
    need(source.get('site_source_sha256') and source.get('vehicle_source_sha256') and
         source.get('camera_plan_sha256') and source.get('camera_pose_review_sha256'),
         'source bindings missing')
    need(isinstance(source.get('exception_sources'), dict) and
         set(source['exception_sources']) == {'traffic_conflict', 'law', 'police_direction', 'device_direction'},
         'exception source inventory missing')
    return source


def audit(plan: dict, comparison_id: str, root: Path, refs: dict) -> dict:
    comparisons = [c for c in plan['comparisons'] if c['comparison_id'] == comparison_id]
    need(len(comparisons) == 1, 'comparison ID absent or duplicated')
    comp = comparisons[0]
    ids = comp['case_ids']
    need(len(ids) == 2 and ids[0] != ids[1], 'exact pair required')
    need(set(refs) == set(ids), 'both exact delivery receipts required')
    left, right = (_case(root, refs[case_id], case_id) for case_id in ids)
    fixed = comp['fixed_conditions']
    changed = comp['deliberate_differences']
    need(set(fixed) == {'cell_id', 'map_name', 'crosswalk_id', 'road_geometry',
                        'vehicle_blueprint', 'camera_plan', 'duration_frames',
                        'all_other_exception_sources'}, 'comparison fixed contract changed')
    need(len(changed) == 1 and changed[0] in {'destination', 'action', 'exception'},
         'comparison variable contract changed')
    need(left['law_id'] == right['law_id'] == plan['law_id'] and
         left['actor'] == right['actor'] == plan['actor'], 'law or actor changed')
    fixed_values = {
        'cell_id': lambda x: x['cell_id'],
        'map_name': lambda x: x['map_name'],
        'crosswalk_id': lambda x: x['crosswalk_id'],
        'road_geometry': lambda x: (x['site_source_sha256'], x['crosswalk_polygon'], x['parking_route']),
        'vehicle_blueprint': lambda x: (x['vehicle_source_sha256'], x['vehicle_blueprint']),
        'camera_plan': lambda x: (x['camera_plan_sha256'],x['camera_pose_review_sha256']),
        'duration_frames': lambda x: x['original_frame_count'],
    }
    for key, get_value in fixed_values.items():
        need(get_value(left) == get_value(right), f'fixed condition changed: {key}')
    selected = right['exception'] if changed == ['exception'] else 'none'
    flag = {'traffic_conflict': 'traffic_conflict', 'law': 'law',
            'police_direction': 'police_direction', 'device_direction': 'device_direction',
            'none': None}[selected]
    for name in left['exception_sources']:
        if name != flag:
            need(left['exception_sources'][name] == right['exception_sources'][name],
                 f'fixed exception source changed: {name}')
    variable = changed[0]
    need(left[variable] != right[variable], f'declared difference absent: {variable}')
    if variable == 'exception':
        need(left['exception'] == 'none' and
             not left['exception_sources'][flag] and right['exception_sources'][flag],
             'selected exception source absent')
    else:
        need(left['exception'] == right['exception'], 'unexpected exception changed')
        other = {'destination', 'action'} - {variable}
        need(all(left[k] == right[k] for k in other), 'undeclared case variable changed')
    return {'format': 'crosswalk-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': ids, 'source_verified': True, 'fixed_checked': fixed,
            'difference_checked': variable, 'delivery_receipt_refs': refs,
            'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--receipts', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(json.loads(args.plan.read_text()), args.comparison,
                   args.root, json.loads(args.receipts.read_text()))
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
