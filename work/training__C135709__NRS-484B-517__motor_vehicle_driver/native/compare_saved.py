"""Compare C135709 stationary reference and contrast under fixed request context."""
import hashlib
import json
from pathlib import Path
import tempfile
import shutil

import measure_saved

CASE=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]

def compare(reference,contrast):
    reference,contrast=Path(reference),Path(contrast)
    a=measure_saved.measure(reference);b=measure_saved.measure(contrast)
    ca=json.loads((reference/'config.json').read_text())
    cb=json.loads((contrast/'config.json').read_text())
    if (ca['candidate_id']!=cb['candidate_id'] or
        ca['case_id'].removesuffix('__reference')!=cb['case_id'].removesuffix('__contrast') or
        ca['road_sha256']!=cb['road_sha256'] or
        ca['camera_policy']!=cb['camera_policy'] or
        ca['motion_policy']!=cb['motion_policy'] or
        ca['approach_frames']!=cb['approach_frames'] or
        a['delivery_ready'] or b['delivery_ready']):
        raise ValueError('C135709 comparison context differs')
    ar=rows(reference/'saved/native-observed.jsonl')
    br=rows(contrast/'saved/native-observed.jsonl')
    ac=rows(reference/'saved/camera-frames.jsonl')
    bc=rows(contrast/'saved/camera-frames.jsonl')
    windows=range(210,240)
    ref_occupied=0;contrast_occupied=0
    for i in windows:
        x,y=ar[i],br[i]
        if (x['frame']!=y['frame'] or x['time_s']!=y['time_s'] or
            x['ego_x_m']!=y['ego_x_m'] or
            x['ego_speed_mps']!=y['ego_speed_mps'] or
            x['ego_speed_mps']>.1 or
            ac[i]['stand_sign_visible']!=bc[i]['stand_sign_visible'] or
            ac[i]['stand_polygon_visible']!=bc[i]['stand_polygon_visible'] or
            ac[i]['camera_frame']!=bc[i]['camera_frame']):
            raise ValueError('C135709 comparison stationary context differs')
        ref_occupied+=all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5
                          for p in x['ego_body_xy_m'])
        contrast_occupied+=all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5
                               for p in y['ego_body_xy_m'])
    expected=0 if ca['candidate_id']=='fallback3' else 30
    if ref_occupied!=0 or contrast_occupied!=expected:
        raise ValueError('C135709 comparison stand occupancy differs')
    return {'candidate_id':ca['candidate_id'],'paired_stationary_frames':30,
        'reference_stand_frames':ref_occupied,'contrast_stand_frames':contrast_occupied,
        'source_hashes':{w:sha(folder/'saved/native-observed.jsonl')
            for w,folder in (('reference',reference),('contrast',contrast))},
        'source_kind':'synthetic_cpu','legal_verdict':None,'delivery_ready':False}

def prove():
    comparisons=[];negatives=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        ref=CASE/'offline/bundles/reference'/candidate
        con=CASE/'offline/bundles/contrast'/candidate
        comparisons.append(compare(ref,con))
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'contrast';shutil.copytree(con,altered)
            path=altered/'saved/native-observed.jsonl'
            lines=path.read_text().splitlines();row=json.loads(lines[220])
            row['ego_speed_mps']=1;lines[220]=json.dumps(row)
            path.write_text('\n'.join(lines)+'\n')
            try:compare(ref,altered)
            except ValueError:pass
            else:raise AssertionError('C135709 altered comparison speed accepted')
        negatives.append({'candidate_id':candidate,'mutation':'stationary_speed',
            'rejected':True})
    proof={'format':'c135709-controlled-saved-comparison-v1',
        'comparisons':comparisons,'negatives':negatives,
        'original_native_observed':False,'legal_verdict':None,'delivery_ready':False}
    (CASE/'native/comparison-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':print(json.dumps({'comparisons':len(prove()['comparisons'])}))
