"""Retain synthetic rotary saved cases and changed-source rejections."""
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,measure,sha

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def build_fixtures():
    folders={}
    for case in ('reference','contrast'):
        request=HERE/'drafts'/case/'primary'/'requested-tracks.jsonl'
        config=json.loads((HERE/'drafts'/case/'primary'/'config.json').read_text())
        folder=HERE/'saved-fixtures'/case
        folder.mkdir(parents=True,exist_ok=True)
        observations=[];frames=[]
        for item in load(request):
            x,y=item['ego_x_m'],item['ego_y_m']
            heading=math.radians(item['ego_heading_deg'])
            forward=(math.cos(heading),math.sin(heading))
            left=(-forward[1],forward[0])
            body=[[round(x+dx*forward[0]+dy*left[0],6),
                   round(y+dx*forward[1]+dy*left[1],6)]
                  for dx,dy in ((-2,-.9),(-2,.9),(2,.9),(2,-.9))]
            observations.append({'frame':item['frame'],'time_s':item['time_s'],
                'native_frame':1000+item['frame'],'source_kind':'synthetic_cpu',
                'case':case,'ego_x_m':x,'ego_y_m':y,
                'ego_heading_deg':item['ego_heading_deg'],
                'ego_speed_mps':item['ego_speed_mps'],
                'lane_id':item['lane_id'],'ego_body_xy_m':body})
            frames.append({'frame':item['frame'],'time_s':item['time_s'],
                'native_frame':1000+item['frame'],'camera_frame':1000+item['frame'],
                'island_visible':True,'source_kind':'synthetic_cpu'})
        write(folder/'native-observed.jsonl',observations)
        write(folder/'island-frames.jsonl',frames)
        (folder/'island-readback.json').write_text(json.dumps({
            'source_kind':'synthetic_cpu','center_xy_m':[0,0],
            'island_radius_m':15,'driving_lane_ids':[-2,-1],
            'road_sha256':config['road_sha256'],
            'physical_island_verified':False,'traffic_control_verified':False},indent=2)+'\n')
        folders[case]=folder
    return folders


def prove():
    folders=build_fixtures()
    positives=[]
    for case,folder in folders.items():
        metric=measure(folder)
        if (metric['case']!=case or not metric['half_circle_passage_observed'] or
                not metric['continuous_requested_side'] or
                metric['island_side_frame_counts']['left' if case=='reference' else 'right']!=240 or
                metric['minimum_body_island_clearance_m']<=0 or
                metric['legal_verdict'] is not None or metric['delivery_ready']):
            raise AssertionError('Synthetic rotary saved measurement differs')
        positives.append({'case':case,'source_hashes':metric['source_hashes'],
                          'measurement':metric})
    negatives=[]
    source=folders['reference']
    for mutation in ('wrong_expected_hash','missing_actor_frame','wrong_motion',
                     'body_inside_island','missing_camera_frame','wrong_road_radius'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            folder=Path(temporary)/'saved';shutil.copytree(source,folder)
            if mutation in ('missing_actor_frame','wrong_motion','body_inside_island'):
                path=folder/'native-observed.jsonl';data=load(path)
                if mutation=='missing_actor_frame':data.pop()
                elif mutation=='wrong_motion':data[60]['ego_speed_mps']=100
                else:data[60]['ego_body_xy_m'][0]=[0,0]
                write(path,data)
            elif mutation=='missing_camera_frame':
                path=folder/'island-frames.jsonl';data=load(path);data.pop();write(path,data)
            elif mutation=='wrong_road_radius':
                path=folder/'island-readback.json';data=json.loads(path.read_text())
                data['island_radius_m']=99;path.write_text(json.dumps(data)+'\n')
            expected={name:sha(folder/name) for name in FILES}
            if mutation=='wrong_expected_hash':expected['native-observed.jsonl']='0'*64
            try:measure(folder,expected if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Changed saved rotary source accepted: '+mutation)
    proof={'format':'c234827-saved-rotary-proof-v1',
        'assignment_id':HERE.parent.name,
        'processor_sha256':sha(HERE/'measure_saved.py'),
        'positives':positives,'negative_controls':negatives,
        'original_native_observed':False,
        'physical_island_verified':False,'legal_verdict':None,'delivery_ready':False}
    (HERE/'saved-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'positives':len(result['positives']),
                                     'negatives':len(result['negative_controls'])}))
