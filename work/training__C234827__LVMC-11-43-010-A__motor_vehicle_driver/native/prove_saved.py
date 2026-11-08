"""Retain synthetic saved rotation passages and altered-source rejections."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,measure,sha

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
OTHER=CASE.parent/'training__C234827__NRS-484B-220-2__motor_vehicle_driver'/'native'/'saved-fixtures'
OUT=HERE/'saved-fixtures'


def write_json(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def write_rows(path,rows):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def build(witness):
    source=OTHER/('reference' if witness=='witness_1' else 'contrast')
    target=OUT/witness;target.mkdir(parents=True)
    original=[json.loads(s) for s in (source/'native-observed.jsonl').read_text().splitlines()]
    observed=[]
    for item in original:
        row={key:value for key,value in item.items() if key!='case'}
        row['witness']=witness
        observed.append(row)
    write_rows(target/'native-observed.jsonl',observed)
    frames=[json.loads(s) for s in (source/'island-frames.jsonl').read_text().splitlines()]
    for row in frames:row['roundabout_visible']=row.pop('island_visible')
    write_rows(target/'roundabout-frames.jsonl',frames)
    write_json(target/'roundabout-readback.json',{
        'source_kind':'synthetic_cpu','center_xy_m':[0,0],
        'island_radius_m':15,'driving_lane_ids':[-2,-1],
        'road_sha256':sha(HERE/'road.xodr'),
        'roundabout_verified':False,'traffic_control_verified':False})
    result=measure(target)
    if (result['source_kind']!='synthetic_cpu' or
            not result['half_circle_passage_observed'] or
            not result['continuous_requested_rotation'] or
            result['occupied_authored_ring_frames']!=240 or
            result['delivery_ready']):
        raise AssertionError('Synthetic LVMC rotation positive differs')
    return {'witness':witness,'source_hashes':result['source_hashes'],
        'measurement':result}


def reject(mutation):
    with tempfile.TemporaryDirectory() as temporary:
        folder=Path(temporary)/'saved';shutil.copytree(OUT/'witness_1',folder)
        if mutation=='wrong_hash':
            expected={name:sha(folder/name) for name in FILES}
            expected['roundabout-frames.jsonl']='0'*64
        else:expected=None
        if mutation in ('missing_actor','reverse_heading','body_inside','wrong_speed'):
            path=folder/'native-observed.jsonl'
            rows=[json.loads(s) for s in path.read_text().splitlines()]
            if mutation=='missing_actor':rows.pop(90)
            elif mutation=='reverse_heading':rows[90]['ego_heading_deg']+=180
            elif mutation=='body_inside':rows[90]['ego_body_xy_m'][0]=[0,0]
            else:rows[90]['ego_speed_mps']+=2
            write_rows(path,rows)
        elif mutation=='missing_camera':
            path=folder/'roundabout-frames.jsonl'
            path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
        try:measure(folder,expected)
        except ValueError:return {'mutation':mutation,'rejected':True}
        raise AssertionError('LVMC saved processor accepted '+mutation)


def prove():
    if OUT.exists():shutil.rmtree(OUT)
    positives=[build(w) for w in ('witness_1','witness_2')]
    negatives=[reject(name) for name in ('wrong_hash','missing_actor',
        'reverse_heading','body_inside','wrong_speed','missing_camera')]
    proof={'format':'c234827-lvmc-saved-proof-v1',
        'assignment_id':CASE.name,'processor_sha256':sha(HERE/'measure_saved.py'),
        'positives':positives,'negative_controls':negatives,
        'original_native_observed':False,'roundabout_verified':False,
        'delivery_ready':False}
    write_json(HERE/'saved-proof.json',proof)
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
        'negatives':len(result['negative_controls'])}))
