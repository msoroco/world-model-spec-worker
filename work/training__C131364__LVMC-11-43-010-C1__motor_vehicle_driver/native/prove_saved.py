"""Retain two synthetic lane-use fixtures and reject altered saved evidence."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import measure, rows

HERE=Path(__file__).resolve().parent
CASE=HERE.parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def build_fixture(witness):
    folder=HERE/'saved-fixtures'/witness
    folder.mkdir(parents=True,exist_ok=True)
    track=HERE/'drafts'/witness/'primary'/'requested-tracks.jsonl'
    source=rows(track)
    observed=[];frames=[]
    for i,row in enumerate(source):
        theta=math.atan2(row['ego_y_m'],row['ego_x_m'])
        r=row['requested_radius_m']
        tangent=(-math.sin(theta),math.cos(theta))
        radial=(math.cos(theta),math.sin(theta))
        body=[]
        for along,across in ((-1,-.5),(-1,.5),(1,-.5),(1,.5)):
            body.append([round(row['ego_x_m']+along*tangent[0]+across*radial[0],6),
                         round(row['ego_y_m']+along*tangent[1]+across*radial[1],6)])
        observed.append({'frame':i,'native_frame':1000+i,'time_s':row['time_s'],
                         'source_kind':'synthetic_cpu','witness':witness,
                         'ego_x_m':row['ego_x_m'],'ego_y_m':row['ego_y_m'],
                         'ego_heading_deg':row['ego_heading_deg'],
                         'ego_speed_mps':row['ego_speed_mps'],'lane_id':row['lane_id'],
                         'ego_body_xy_m':body,'actual_exit_observed':False,
                         'derived_request_sha256':sha(track)})
        frames.append({'frame':i,'camera_frame':1000+i,'time_s':row['time_s'],
                       'source_kind':'synthetic_cpu','left_lane_visible':True})
    (folder/'native-observed.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in observed))
    (folder/'camera-frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
    readback={'source_kind':'synthetic_cpu','road_sha256':sha(HERE/'road.xodr'),
              'driving_lane_ids':[-2,-1],'left_lane_id':-1,'right_lane_id':-2,
              'physical_roundabout_verified':False,'exit_connector_verified':False}
    (folder/'lane-readback.json').write_text(json.dumps(readback,indent=2)+'\n')
    return folder

def reject(folder,mutation):
    with tempfile.TemporaryDirectory(dir=HERE) as temporary:
        changed=Path(temporary)/'fixture';shutil.copytree(folder,changed)
        if mutation=='wrong_hash':
            hashes={name:sha(folder/name) for name in ('native-observed.jsonl','lane-readback.json','camera-frames.jsonl')}
            hashes['native-observed.jsonl']='0'*64
            try:measure(changed,hashes)
            except ValueError:return True
        elif mutation=='wrong_lane':
            path=changed/'native-observed.jsonl';data=rows(path)
            data[40]['lane_id']=-2 if data[40]['lane_id']==-1 else -1
            path.write_text(''.join(json.dumps(row)+'\n' for row in data))
            try:measure(changed)
            except ValueError:return True
        elif mutation=='missing_camera':
            path=changed/'camera-frames.jsonl';data=rows(path)[:-1]
            path.write_text(''.join(json.dumps(row)+'\n' for row in data))
            try:measure(changed)
            except ValueError:return True
    raise ValueError(f'C131364 saved mutation accepted: {mutation}')

def prove():
    positives=[]
    for witness in ('witness_1','witness_2'):
        folder=build_fixture(witness)
        measurement=measure(folder)
        if measurement['full_body_requested_lane_frames']!=240 or measurement['actual_left_exit_observed']:
            raise ValueError('C131364 synthetic lane occupancy differs')
        positives.append({'witness':witness,'measurement':measurement})
    negatives=[]
    for mutation in ('wrong_hash','wrong_lane','missing_camera'):
        for witness in ('witness_1','witness_2'):
            reject(HERE/'saved-fixtures'/witness,mutation)
            negatives.append({'witness':witness,'mutation':mutation,'rejected':True})
    result={'format':'c131364-saved-proof-v1','positives':positives,
            'negative_controls':negatives,'original_native_observed':False,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (HERE/'saved-proof.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'positives':len(prove()['positives'])}))
