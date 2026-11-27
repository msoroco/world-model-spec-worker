"""Compare independently audited original caravan and motorcade cases."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from runner import AID

HERE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_comparison(comparison_id, paths):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    matches = [item for item in plan['comparisons'] if item['comparison_id'] == comparison_id]
    require(len(matches) == 1, 'unknown exact group comparison')
    expected = matches[0]['case_ids']
    require(set(paths) == set(expected) and len(paths) == len(expected),
            'comparison must include every exact group case once')
    audits = []
    digests = {}
    for case_id in expected:
        path = Path(paths[case_id])
        require(path.is_file() and not path.is_symlink(), 'original group audit missing')
        item = json.loads(path.read_text())
        require(item.get('format') == 'c160013-original-delivery-audit-v1'
                and item.get('case_id') == case_id
                and item.get('original_frame_count') == 600
                and item.get('legal_status') == 'unresolved'
                and item.get('source_sha256', {}).get('capture-seal.json')
                and item.get('measurement', {}).get('legal_judgment') == 'unresolved',
                'source-bound exact original group audit required')
        audits.append(item)
        digests[case_id] = hashlib.sha256(path.read_bytes()).hexdigest()
    contexts = [item['original_context'] for item in audits]
    measurements = [item['measurement'] for item in audits]
    for key in ('native_road_id', 'directed_driving_lane_id',
                'public_highway_source', 'outside_business_district_source',
                'weather_sha256', 'vehicle_blueprints_sha256'):
        require(len({str(context.get(key)) for context in contexts}) == 1 and contexts[0].get(key),
                'fixed original road, region, weather or vehicle source changed: ' + key)
    if comparison_id.endswith('_spacing'):
        require(len(audits) == 3, 'three original spacing points required')
        for key in ('group_kind', 'group_towing', 'entrant_kind', 'coordination_source'):
            require(len({str(context.get(key)) for context in contexts}) == 1,
                    'spacing control changed: ' + key)
        requested = [item['requested_gap_m'] for item in measurements]
        front = [item['steady_front_mean_m'] for item in measurements]
        rear = [item['steady_rear_mean_m'] for item in measurements]
        require(requested[0] < requested[1] < requested[2] and
                front[0] < front[1] < front[2] and rear[0] < rear[1] < rear[2],
                'original full-body spacing order missing')
        proof = {'requested_gap_m':requested, 'measured_front_gap_m':front,
                 'measured_rear_gap_m':rear}
    elif comparison_id.endswith('_towing'):
        require(len(audits) == 2 and
                contexts[0]['group_towing'] is False and contexts[1]['group_towing'] is True,
                'group towing alternative not isolated')
        for key in ('group_kind', 'entrant_kind', 'coordination_source'):
            require(contexts[0][key] == contexts[1][key], 'towing control changed: ' + key)
        require(measurements[0]['requested_gap_m'] == measurements[1]['requested_gap_m'],
                'towing comparison changed requested gap')
        proof = {'group_towing':[False, True]}
    elif comparison_id.endswith('_entrant'):
        require(len(audits) == 2 and
                [context['entrant_kind'] for context in contexts] == ['vehicle','combination'],
                'entrant combination alternative not isolated')
        for key in ('group_kind', 'group_towing', 'coordination_source'):
            require(contexts[0][key] == contexts[1][key], 'entrant control changed: ' + key)
        require(measurements[0]['requested_gap_m'] == measurements[1]['requested_gap_m'],
                'entrant comparison changed requested gap')
        proof = {'entrant_kind':['vehicle','combination']}
    elif comparison_id.startswith('group_kind_'):
        require(len(audits) == 2 and
                [context['group_kind'] for context in contexts] == ['caravan','motorcade'],
                'caravan versus motorcade alternative not isolated')
        require(contexts[0]['coordination_source'] != contexts[1]['coordination_source'],
                'independent group relationship source did not vary')
        for key in ('group_towing','entrant_kind'):
            require(contexts[0][key] == contexts[1][key], 'group kind control changed: ' + key)
        require(measurements[0]['requested_gap_m'] == measurements[1]['requested_gap_m'],
                'group kind comparison changed requested gap')
        proof = {'group_kind':['caravan','motorcade']}
    else:
        raise ValueError('unknown group comparison type')
    return {'format':'c160013-original-comparison-audit-v1',
        'assignment_id':AID,'comparison_id':comparison_id,'case_ids':expected,
        'case_audit_sha256':digests,'comparison_proof':proof,
        'fixed_native_road_id':contexts[0]['native_road_id'],
        'sufficient_space':'unresolved','without_danger':'unresolved',
        'legal_status':'unresolved'}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--audit', action='append', nargs=2,
                        metavar=('CASE_ID','PATH'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args=parser.parse_args()
    pairs=dict(args.audit)
    require(len(pairs) == len(args.audit), 'duplicate group case audit')
    if args.output.exists():
        raise ValueError('retain prior comparison audit')
    args.output.write_text(json.dumps(audit_comparison(args.comparison,pairs),indent=2)+'\n')
