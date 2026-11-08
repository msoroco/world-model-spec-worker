"""Independent source reconstruction and trigger-threshold audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proof = json.loads((HERE/'trigger-proof.json').read_text())
assert proof['build_manifest_sha256']==sha(HERE/'drafts/manifest.json')
assert proof['trigger_code_sha256']==sha(HERE/'triggers.py')
assert len(proof['fixtures'])==12 and proof['negative_hash_rejections']==2
seen=set()
for fixture in proof['fixtures']:
    case,candidate,expected=fixture['case'],fixture['candidate'],fixture['expected']
    assert (case,candidate,expected) not in seen
    seen.add((case,candidate,expected))
    path=HERE/fixture['observed_path']
    assert fixture['observed_sha256']==sha(path)
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows)==480
    policy='fallback1' if case=='contrast' and not expected and candidate in ('fallback1','fallback2') else 'primary'
    requests=[json.loads(line) for line in (HERE/'drafts'/case/policy/'requested-tracks.jsonl').read_text().splitlines()]
    assert len(requests)==480
    overlap=[]; inside=[]; offcenter=[]
    for i,(row,request) in enumerate(zip(rows,requests)):
        x,y=request['requested_center_xy_m']; y=-y
        expected_body=[[x+dx,round(y+dy,4)] for dx,dy in
                       ((-4,-1.2),(-4,1.2),(4,-1.2),(4,1.2))]
        if case=='reference' and expected and candidate=='fallback1' and i==120:
            for p in expected_body:p[1]=round(p[1]+3,4)
        if case=='reference' and expected and candidate=='fallback2':
            for p in expected_body:p[1]=round(p[1]+.4,4)
        assert row['body_native_xy_m']==expected_body
        assert row['frame']==i and row['native_frame']==1000+i
        assert abs(row['time_s']-(.05+i/20))<1e-4
        assert row['source_kind']=='synthetic_cpu'
        assert row['vehicle_blueprint']=='vehicle.carlamotors.carlacola'
        assert row['speed_mps']==request['requested_speed_mps']
        ys=[p[1] for p in expected_body]; ymin,ymax=min(ys),max(ys)
        if row['speed_mps']>.1:
            if ymax>3.5 and ymin<7.5:overlap.append(i)
            if ymin>=3.5 and ymax<=7.5:inside.append(i)
            if abs(sum(ys)/4-1.75)>.25:offcenter.append(i)
    metric=fixture['metric']
    if candidate=='fallback1':
        assert metric=={'first_moving_overlap_frame':overlap[0] if overlap else None,
                        'threshold_frame':65 if case=='contrast' else None,
                        'reference_unsafe_overlap':case=='reference'}
        calculated=bool(overlap) if case=='reference' else not overlap or overlap[0]>65
    elif candidate=='fallback2':
        assert metric=={'moving_full_body_inside_frames':len(inside),
                        'moving_offcenter_frames':len(offcenter),
                        'threshold_frames':400 if case=='contrast' else 0}
        calculated=bool(offcenter) if case=='reference' else len(inside)<400
    else:
        camera=fixture['camera']
        assert camera['sha256']==sha(Path(camera['source']))
        assert camera['source_kind']=='synthetic_cpu' and camera['frames']==480
        visible=camera['visible_frames']
        assert metric=={'visible_fraction':visible/480,'threshold_fraction':.75,
                        'camera_source_sha256':camera['sha256']}
        calculated=visible/480<.75
    assert calculated is expected
assert len(seen)==12 and proof['original_native_observed'] is False
assert proof['delivery_or_legal_result'] is False
audit={'format':'c422978-heavy-native-trigger-audit-v1','passed':True,
       'proof_sha256':sha(HERE/'trigger-proof.json'), 'fixtures':12,
       'raw_rows_reconstructed':5760,'source_hash_negatives':2,
       'physical_or_legal_result_proven':False}
(HERE/'trigger-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print('heavy trigger independent audit: 12 fixtures, 5760 rows')
