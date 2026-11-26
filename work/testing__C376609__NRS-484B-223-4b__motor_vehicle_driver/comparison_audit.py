"""Independent source-bound exact comparison; no legal determination."""
import argparse
import json
from pathlib import Path

FIXED = ('public_highway_source_sha256', 'driver_actor_id', 'vehicle_blueprint',
         'camera_plan_sha256', 'duration_frames')


def audit(plan, comparison_id, records, *, diagnostic=False):
    selected = [x for x in plan['comparisons'] if x['comparison_id'] == comparison_id]
    if len(selected) != 1:
        raise ValueError('unknown exact comparison')
    spec = selected[0]
    ids = spec['case_ids']
    if set(records) != set(ids) or len(ids) != 2:
        raise ValueError('exact comparison case identities differ')
    pair = [records[x] for x in ids]
    for case_id, row in zip(ids, pair):
        if row.get('case_id') != case_id or row.get('format') != 'worker-independent-original-delivery-measurement':
            raise ValueError('source-bound delivery measurement missing')
        if row.get('frame_count') != 900 or row.get('full_video_decode') is not True:
            raise ValueError('full original motion and pixels required')
        if row.get('diagnostic_fixture') is not diagnostic:
            raise ValueError('diagnostic/original provenance differs')
        if not diagnostic and not row.get('source_verified'):
            raise ValueError('independently reviewed original source required')
        for field in FIXED:
            if row.get(field) in (None, ''):
                raise ValueError('missing fixed condition: ' + field)
    if pair[0].get('result_sha256') == pair[1].get('result_sha256'):
        raise ValueError('two independent captures required')
    for field in FIXED:
        if pair[0][field] != pair[1][field]:
            raise ValueError('fixed comparison condition changed: ' + field)
    if comparison_id not in ('lane_design', 'right_lane_count', 'alley') and pair[0].get('map_sha256') != pair[1].get('map_sha256'):
        raise ValueError('source map changed outside deliberate design comparison')
    for field in spec['deliberate_differences']:
        values = [row.get('observables', {}).get(field) for row in pair]
        if None in values or json.dumps(values[0], sort_keys=True) == json.dumps(values[1], sort_keys=True):
            raise ValueError('deliberate original difference absent: ' + field)
    return {'format': 'worker-exact-comparison-audit', 'comparison_id': comparison_id,
            'case_ids': ids, 'diagnostic_fixture': diagnostic,
            'source_verified': not diagnostic, 'legal_verdict': None}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--comparison', required=True)
    ap.add_argument('--records', type=Path, required=True)
    ap.add_argument('--diagnostic', action='store_true')
    args = ap.parse_args()
    plan = json.loads((Path(__file__).parent / 'case-plan.json').read_text())
    print(json.dumps(audit(plan, args.comparison, json.loads(args.records.read_text()), diagnostic=args.diagnostic), indent=2))
