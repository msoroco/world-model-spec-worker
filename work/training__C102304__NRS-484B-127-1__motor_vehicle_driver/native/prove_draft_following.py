"""Generate unselected, source-bound synthetic following measurements.

These are authored CPU fixtures, never CARLA observations or accepted recordings.
"""
import copy
import json
from pathlib import Path
import tempfile

from geometry import (DURATION_S, EGO_HALF_LENGTH_M, EGO_HALF_WIDTH_M,
                      GAP_TARGET_M, LANE_ID, LANE_Y_M, LEAD_HALF_LENGTH_M,
                      LEAD_HALF_WIDTH_M, RATE_HZ, ROAD_ID, SPEED_MPS, body,
                      check, positions)
from measure_following import measure

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'draft-following'


def row(suffix, index):
    ego_x, lead_x = positions(suffix, index)
    def vehicle(x, half_length, half_width):
        return {'native_road_id': ROAD_ID, 'native_lane_id': LANE_ID,
                'native_forward_xy': [1.0, 0.0], 'speed_mps': SPEED_MPS,
                'native_body_xy_m': body(x, LANE_Y_M, half_length, half_width)}
    return {'native_frame': index+1, 'time_s': round((index+1)/RATE_HZ, 5),
            'ego': vehicle(ego_x, EGO_HALF_LENGTH_M, EGO_HALF_WIDTH_M),
            'lead': vehicle(lead_x, LEAD_HALF_LENGTH_M, LEAD_HALF_WIDTH_M)}


def context():
    return {'source_kind': 'synthetic_scene_request',
            'native_road_id': ROAD_ID, 'native_lane_id': LANE_ID,
            'hill_crest_profile': 'authored 0-to-4-to-0 m elevation, not Native verified',
            'traffic': 'requested moving lead only; observed traffic unknown',
            'surface': 'requested dry pavement; observed highway condition unknown',
            'visibility': 'requested clear; observed sight distance unknown',
            'highway_public_availability': 'unverified; geometry alone cannot establish public availability',
            'apparatus_response_status': 'unverified; no emergency privilege inferred',
            'ego_emergency_business_status': 'ordinary driver requested; physical status unverified'}


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(r, sort_keys=True, separators=(',', ':'))+'\n'
                            for r in rows))


def rejected(label, rows, ctx):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        samples, context_path = root/'native_samples.jsonl', root/'following_context.json'
        if rows is not None:
            write_rows(samples, rows)
        if ctx is not None:
            context_path.write_text(json.dumps(ctx, sort_keys=True))
        try:
            measure(samples, context_path)
        except ValueError as error:
            return {'negative': label, 'rejected': True, 'error': str(error)}
        raise AssertionError('Negative accepted: '+label)


def main():
    geometry = check()
    OUT.mkdir(exist_ok=True)
    reports = {}
    for suffix, gap in GAP_TARGET_M.items():
        case_dir = OUT/suffix
        case_dir.mkdir(exist_ok=True)
        rows = [row(suffix, i) for i in range(RATE_HZ*DURATION_S)]
        source = case_dir/'native_samples.jsonl'
        ctx_path = case_dir/'following_context.json'
        write_rows(source, rows)
        ctx_path.write_text(json.dumps(context(), indent=2, sort_keys=True)+'\n')
        receipt = measure(source, ctx_path)
        assert receipt['original_frames'] == 900
        assert receipt['following_duration_s'] == 45
        assert receipt['min_bumper_gap_m'] == gap
        assert receipt['median_bumper_gap_m'] == gap
        assert receipt['median_time_headway_s'] == round(gap/SPEED_MPS, 6)
        (case_dir/'measurement.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n')
        reports[suffix] = receipt
    rows = [row('condition_a', i) for i in range(RATE_HZ*DURATION_S)]
    bad_lead = copy.deepcopy(rows)
    bad_lead[10]['lead']['speed_mps'] = 0.0
    bad_lane = copy.deepcopy(rows)
    bad_lane[10]['lead']['native_lane_id'] = 1
    missing_context = context()
    del missing_context['traffic']
    negatives = [rejected('missing_samples', None, context()),
                 rejected('stationary_lead', bad_lead, context()),
                 rejected('wrong_lead_lane', bad_lane, context()),
                 rejected('missing_traffic_context', rows, missing_context)]
    summary = {'scope': 'authored synthetic only; no Native realization or legal finding',
               'geometry': geometry, 'measurements': reports, 'negatives': negatives}
    (OUT/'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'frames_per_case': 900, 'gaps_m': {k: v['median_bumper_gap_m'] for k,v in reports.items()},
                      'headways_s': {k: v['median_time_headway_s'] for k,v in reports.items()},
                      'negative_rejections': len(negatives)}, sort_keys=True))


if __name__ == '__main__':
    main()
