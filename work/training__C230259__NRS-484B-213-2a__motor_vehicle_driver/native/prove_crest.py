"""Generate source-shaped 30-second packets and negative tests, under ignored root."""
import json
from pathlib import Path
from measure_crest import measure, sha

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT/'.runtime-work/c230259-213-2a'
OUT.mkdir(parents=True, exist_ok=True)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True, separators=(',', ':'))+'\n')


def packet(name, left_start=None, one_way=False):
    folder = OUT/name
    folder.mkdir(exist_ok=True)
    road = folder/'road.json'
    trace = folder/'native-raw.jsonl'
    write(road, {'directionality': 'one_way' if one_way else 'two_way', 'center_y_m': 0,
                 'crest_x_m': 120, 'grade_profile_source': 'road.xodr elevationProfile s=300,450,600; illustrative source readback'})
    with trace.open('w') as stream:
        for i in range(600):
            left = left_start is not None and left_start <= i < 380
            x = 60 + 0.12*i
            y = -0.5 if left else 2.0
            write_row = {'frame': i, 'ego_id': 'ego', 'ego_x_m': x, 'ego_forward_mps': 2.4,
                         'ego_bbox_y_min_m': y-0.6, 'ego_bbox_y_max_m': y+0.6,
                         'sight_clear_m': 48 if 230 <= i <= 420 else 220,
                         'sight_censored': not (230 <= i <= 420),
                         'other_vehicle_id': 'opponent', 'other_vehicle_direction': 'opposing',
                         'other_vehicle_x_m': 180-0.1*i,
                         'camera_frame_ids': {c: i for c in ('overview','approach','reference_corner','driver_reference')}}
            stream.write(json.dumps(write_row, sort_keys=True, separators=(',', ':'))+'\n')
    return trace, road


def main():
    results = {}
    for name, start, one_way in [('right_two_way',None,False), ('left_two_way',260,False),
                                 ('left_one_way',260,True), ('earlier_left_entry',100,False)]:
        trace, road = packet(name, start, one_way)
        results[name] = measure(trace, road)
    assert results['right_two_way']['approach_left_overlap_count'] == 0
    assert results['left_two_way']['approach_left_overlap_count'] > 0
    assert results['left_one_way']['one_way_exception_observed']
    assert results['earlier_left_entry']['approach_left_overlap_count'] > 0
    trace, road = packet('negative',260,False)
    lines = trace.read_text().splitlines()
    for label, change in [('drop_frame',lambda p: None), ('camera_misjoin',lambda p: p.update(camera_frame_ids={**p['camera_frame_ids'],'overview':-1})),
                          ('missing_sight',lambda p: p.pop('sight_clear_m'))]:
        bad = OUT/f'{label}.jsonl'
        changed = list(lines)
        if label == 'drop_frame':
            changed.pop(299)
        else:
            p=json.loads(changed[299]);change(p);changed[299]=json.dumps(p)
        bad.write_text('\n'.join(changed)+'\n')
        try:
            measure(bad,road)
        except ValueError:
            pass
        else:
            raise AssertionError(f'{label} accepted')
    proof = {'format':'worker-crest-source-proof-v1','assignment_id':HERE.parent.name,
             'cases':results,'negative_rejections':['drop_frame','camera_misjoin','missing_sight'],
             'source_kind':'source-shaped CPU fixture; no Native execution',
             'original_native_observed':False}
    dest = HERE/'crest-source-proof.json'
    dest.write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({'proof_sha256':sha(dest),'case_count':len(results),'negative_count':3}))

if __name__ == '__main__':
    main()
