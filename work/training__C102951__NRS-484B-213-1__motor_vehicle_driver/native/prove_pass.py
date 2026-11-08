"""Three synthetic clear-ahead probes with saved pass positives and negatives."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from measure_pass import measure

HERE=Path(__file__).resolve().parent
DISTANCES=(70,120,170)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path,rows):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def lateral(i):
    if i<30:return -1.75
    if i<50:return -1.75+3.5*(i-30)/20
    if i<115:return 1.75
    if i<140:return 1.75-3.5*(i-115)/25
    return -1.75


def fixture(distance):
    folder=HERE/'saved-fixtures'/str(distance);folder.mkdir(parents=True,exist_ok=True)
    road={'format':'c102951-road-readback-v1','lane_count':2,'travel_directions':2,
          'centerline_y_m':0,'crest_profile':'authored_synthetic_probe',
          'highway_status_reviewed':False,'source_kind':'synthetic_cpu'}
    (folder/'road-readback.json').write_text(json.dumps(road,indent=2)+'\n')
    entry=next(i for i in range(480) if lateral(i)+.9>0)
    oncoming_at_zero=.8*entry+4.4+distance+.6*entry
    rows=[]
    for i in range(480):
        rows.append({'frame':i,'native_frame':1000+i,'time_s':round(.05+i/20,4),
                     'source_kind':'synthetic_cpu','ego_blueprint':'vehicle.tesla.model3',
                     'ego_x_m':round(.8*i,4),'ego_y_m':round(lateral(i),4),'ego_speed_mps':16,
                     'overtaken_x_m':round(30+.4*i,4),'overtaken_y_m':-1.75,'overtaken_speed_mps':8,
                     'oncoming_x_m':round(oncoming_at_zero-.6*i,4),'oncoming_y_m':1.75,
                     'oncoming_speed_mps':12,'driver_eye_clear_m':distance,
                     'sightline_visible':True})
    write_rows(folder/'native-observed.jsonl',rows)
    return folder


def rejected(fn):
    try:fn()
    except (ValueError,TypeError):return True
    raise AssertionError('Altered saved pass accepted')


def prove():
    positives=[];negatives=[]
    for distance in DISTANCES:
        folder=fixture(distance)
        result=measure(folder)
        if (result['entry_oncoming_body_gap_m']!=distance or
                result['minimum_left_phase_driver_eye_clear_m']!=distance or
                result['legal_verdict'] is not None or result['safe_distance_judgment'] is not None):
            raise AssertionError('Synthetic clear-ahead probe differs')
        positives.append({'requested_clear_oncoming_distance_m':distance,'measurement':result})
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            copy=Path(temporary)/'attempt';shutil.copytree(folder,copy)
            rows=[json.loads(line) for line in (copy/'native-observed.jsonl').read_text().splitlines()]
            negatives.append({'distance_m':distance,'mutation':'source_hash',
                              'rejected':rejected(lambda:measure(copy,{'native-observed.jsonl':'0'*64,
                                                                     'road-readback.json':sha(copy/'road-readback.json')}))})
            for name,alter in (
                ('time_join',lambda r:r[37].update(time_s=99)),
                ('no_return',lambda r:[row.update(ego_y_m=1.75) for row in r[115:]]),
                ('wrong_oncoming_side',lambda r:r[38].update(oncoming_y_m=-1.75)),
                ('missing_sightline',lambda r:r[38].pop('sightline_visible'))):
                mutated=json.loads(json.dumps(rows));alter(mutated)
                write_rows(copy/'native-observed.jsonl',mutated)
                negatives.append({'distance_m':distance,'mutation':name,
                                  'rejected':rejected(lambda:measure(copy))})
            road=json.loads((copy/'road-readback.json').read_text());road['travel_directions']=1
            (copy/'road-readback.json').write_text(json.dumps(road)+'\n')
            negatives.append({'distance_m':distance,'mutation':'road_direction',
                              'rejected':rejected(lambda:measure(copy))})
    proof={'format':'c102951-saved-pass-cpu-proof-v1','assignment_id':HERE.parent.name,
           'assignment_sha256':sha(HERE.parent.parent.parent/'inputs'/HERE.parent.name/'assignment.json'),
           'case_plan_sha256':sha(HERE.parent/'case-plan.json'),
           'processor_sha256':sha(HERE/'measure_pass.py'),
           'positives':positives,'negatives':negatives,
           'original_native_observed':False,'safe_distance_judgment':None,
           'delivery_ready':False}
    (HERE/'pass-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),'negatives':len(result['negatives'])}))
