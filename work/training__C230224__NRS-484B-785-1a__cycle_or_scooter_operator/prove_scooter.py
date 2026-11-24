"""Run 600-frame positive/negative measurement fixtures outside work/."""
import json
import os
from pathlib import Path
import tempfile
from measure_scooter import AID, measure


def fixture(root, speed):
    root.mkdir()
    frame = root / 'video_frames.jsonl'
    trace = root / 'native_rider_trace.jsonl'
    with frame.open('w') as f, trace.open('w') as t:
        for i in range(600):
            f.write(json.dumps({'video_frame': i, 'native_frame': 100+i, 'time_s': i*.05})+'\n')
            t.write(json.dumps({'video_frame': i, 'native_frame': 100+i,
                'source_kind': 'synthetic_native_sample', 'device_actor_id': 1,
                'rider_actor_id': 2, 'device_center_xy_m': [i*.1, 0],
                'device_speed_mps': speed})+'\n')
    ctx = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
        'device_subtype': 'electric_scooter', 'device_actor_id': 1,
        'rider_actor_id': 2, 'path_box_xyxy_m': [-1,-2,61,2],
        'scooter_rider_excluded_mass_lb': 45, 'scooter_motor_only_max_mph': 18,
        'ordinance_exception_reviewed': True, 'path_access_reviewed': True}
    for key in ('scooter_classification_source', 'scooter_mass_source', 'scooter_motor_max_speed_source',
                'path_surface_source', 'path_continuity_source', 'path_access_source',
                'roadway_boundary_source', 'ordinance_applicability_source', 'ordinance_review_source'):
        ctx[key] = 'synthetic-fixture:'+key
    (root / 'scooter_context.json').write_text(json.dumps(ctx)+'\n')


def must_reject(path):
    try:
        measure(path)
    except ValueError:
        return
    raise AssertionError('Source defect accepted')


def main():
    scratch = Path(os.environ['TMPDIR'])
    with tempfile.TemporaryDirectory(prefix='scooter-proof-', dir=scratch) as t:
        p = Path(t)
        low, high = p/'low', p/'high'
        fixture(low, 12*.44704)
        fixture(high, 17*.44704)
        a, b = measure(low), measure(high)
        assert a['above_15_mph_frames'] == 0 and b['above_15_mph_frames'] == 600
        assert a['path_center_frames'] == b['path_center_frames'] == 600
        c = json.loads((low/'scooter_context.json').read_text())
        c['device_subtype'] = 'bicycle'
        (low/'scooter_context.json').write_text(json.dumps(c)+'\n')
        must_reject(low)
        c['device_subtype'] = 'electric_scooter'
        c['ordinance_exception_reviewed'] = False
        (low/'scooter_context.json').write_text(json.dumps(c)+'\n')
        must_reject(low)
        c['ordinance_exception_reviewed'] = True
        c['scooter_motor_only_max_mph'] = 25
        (low/'scooter_context.json').write_text(json.dumps(c)+'\n')
        must_reject(low)
        row = (high/'native_rider_trace.jsonl').read_text().splitlines()
        x = json.loads(row[50]); x['rider_actor_id'] = 3; row[50] = json.dumps(x)
        (high/'native_rider_trace.jsonl').write_text('\n'.join(row)+'\n')
        must_reject(high)
        print(json.dumps({'low_mph': a['max_speed_mph'], 'high_mph': b['max_speed_mph'],
                          'negative_source_checks': 4, 'legal_result': None}, sort_keys=True))


if __name__ == '__main__':
    main()
