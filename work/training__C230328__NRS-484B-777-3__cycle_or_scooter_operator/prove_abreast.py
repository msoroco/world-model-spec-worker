"""Synthetic diagnostics for saved rider geometry and source rejection."""
import json
import os
from pathlib import Path
import tempfile
from measure_abreast import AID, measure


def fixture(root, n, convoy=False):
    root.mkdir()
    ids = list(range(1,n+1))
    context = {'assignment_id':AID,'review_kind':'synthetic_diagnostic','reviewer':'synthetic fixture',
        'rider_ids':ids,'device_subtypes':{str(i):'bicycle' for i in ids},
        'exclusive_use_reviewed':True}
    for key in ('public_dedication_source','public_vehicle_access_source','roadway_boundary_source',
        'shoulder_boundary_source','exclusive_use_source','exclusive_use_review_source',
        'rider_device_source','bicycle_wheel_source','bicycle_diameter_source','bicycle_moped_exclusion_source'):
        context[key]='synthetic-fixture:'+key
    (root/'road_context.json').write_text(json.dumps(context)+'\n')
    with (root/'video_frames.jsonl').open('w') as frames, (root/'rider_poses.jsonl').open('w') as poses:
        for i in range(600):
            frames.write(json.dumps({'video_frame':i,'native_frame':100+i,'time_s':i*.05})+'\n')
            riders = [{'rider_id':j,'longitudinal_m':i*.1+(j*6 if convoy else 0),
                'lateral_m':j*1.5,'half_length_m':.8,'speed_mps':2,
                'roadway_occupied':True,'shoulder_occupied':False,'exclusive_use_occupied':False} for j in ids]
            poses.write(json.dumps({'video_frame':i,'native_frame':100+i,
                'source_kind':'synthetic_native_sample','riders':riders})+'\n')


def reject(root):
    try:
        measure(root)
    except ValueError:
        return
    raise AssertionError('Source defect accepted')


def main():
    with tempfile.TemporaryDirectory(prefix='abreast-proof-',dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)
        two,three,convoy=root/'two',root/'three',root/'convoy'
        fixture(two,2);fixture(three,3);fixture(convoy,3,True)
        a,b,c=measure(two),measure(three),measure(convoy)
        assert a['rider_count']==2 and b['rider_count']==c['rider_count']==3
        assert len(b['per_frame_geometry'][0]['pairwise'])==3
        assert all(x['overlap_length_m']==0 for x in c['per_frame_geometry'][0]['pairwise'])
        assert b['abreast_classification'] is None and c['legal_result'] is None
        ctx=json.loads((two/'road_context.json').read_text());ctx['exclusive_use_reviewed']=False
        (two/'road_context.json').write_text(json.dumps(ctx)+'\n');reject(two)
        line=(three/'rider_poses.jsonl').read_text().splitlines();row=json.loads(line[44]);row['riders'][2]['roadway_occupied']=False;line[44]=json.dumps(row)
        (three/'rider_poses.jsonl').write_text('\n'.join(line)+'\n');reject(three)
        line=(convoy/'rider_poses.jsonl').read_text().splitlines();row=json.loads(line[20]);row['riders'][0]['rider_id']=9;line[20]=json.dumps(row)
        (convoy/'rider_poses.jsonl').write_text('\n'.join(line)+'\n');reject(convoy)
        print(json.dumps({'two_riders_pairs':1,'three_riders_pairs':3,'convoy_overlap_pairs':0,
                          'negative_source_checks':3,'abreast_classification':None,'legal_result':None},sort_keys=True))


if __name__=='__main__':main()
