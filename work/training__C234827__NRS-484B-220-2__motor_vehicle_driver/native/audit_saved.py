"""Independent 480-row rotary saved audit and negative replay."""
import json
import math
from pathlib import Path
import shutil
import tempfile

from measure_saved import FILES,measure,sha

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def audit():
    proof_path=HERE/'saved-proof.json'
    proof=json.loads(proof_path.read_text())
    mutations=['wrong_expected_hash','missing_actor_frame','wrong_motion',
               'body_inside_island','missing_camera_frame','wrong_road_radius']
    if (proof['format']!='c234827-saved-rotary-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['processor_sha256']!=sha(HERE/'measure_saved.py') or
            len(proof['positives'])!=2 or
            [row['mutation'] for row in proof['negative_controls']]!=mutations or
            not all(row['rejected'] is True for row in proof['negative_controls']) or
            proof['original_native_observed'] or proof['physical_island_verified'] or
            proof['legal_verdict'] is not None or proof['delivery_ready']):
        raise ValueError('Rotary saved proof provenance differs')
    checked=0;seen=set()
    for item in proof['positives']:
        case=item['case'];folder=HERE/'saved-fixtures'/case
        if case not in ('reference','contrast') or case in seen:
            raise ValueError('Rotary saved case coverage differs')
        seen.add(case)
        hashes={name:sha(folder/name) for name in FILES}
        if hashes!=item['source_hashes']:
            raise ValueError('Rotary saved source bytes differ')
        observed=load(folder/'native-observed.jsonl')
        frames=load(folder/'island-frames.jsonl')
        island=json.loads((folder/'island-readback.json').read_text())
        if (len(observed)!=240 or len(frames)!=240 or
                island['center_xy_m']!=[0,0] or island['island_radius_m']!=15 or
                island['physical_island_verified']):
            raise ValueError('Rotary saved readback differs')
        direction=1 if case=='reference' else -1
        progress=0.0;previous=None;minimum=float('inf');max_offset=0;visible=0;entry_visible=0
        for i,(row,frame) in enumerate(zip(observed,frames)):
            x,y=row['ego_x_m'],row['ego_y_m']
            theta=math.atan2(y,x)
            heading=math.radians(row['ego_heading_deg'])
            cross=math.cos(heading)*(-y)-math.sin(heading)*(-x)
            if (row['frame']!=i or frame['frame']!=i or
                    row['native_frame']!=1000+i or
                    frame['camera_frame']!=row['native_frame'] or
                    frame['time_s']!=row['time_s'] or
                    row['case']!=case or row['lane_id']!=-1 or
                    row['ego_speed_mps']!=8 or
                    row['source_kind']!='synthetic_cpu' or
                    frame['source_kind']!='synthetic_cpu' or
                    direction*cross<=1):
                raise ValueError('Independent rotary saved row differs')
            if previous is not None:
                progress+=math.atan2(math.sin(theta-previous),math.cos(theta-previous))
            previous=theta
            for point in row['ego_body_xy_m']:
                if math.hypot(point[0]-x,point[1]-y)>3.5:
                    raise ValueError('Independent rotary body vertex detached')
                minimum=min(minimum,math.hypot(*point)-15)
            max_offset=max(max_offset,abs(math.hypot(x,y)-23.75))
            visible+=frame['island_visible']
            if i<40:entry_visible+=frame['island_visible']
            checked+=1
        metric=item['measurement']
        if (metric['source_hashes']!=hashes or
                metric['angular_progress_rad']!=round(progress,4) or
                metric['half_circle_passage_observed'] is not True or
                metric['continuous_requested_side'] is not True or
                metric['island_side_frame_counts']!=
                    {'left':240 if case=='reference' else 0,
                     'right':240 if case=='contrast' else 0,'ambiguous':0} or
                metric['minimum_body_island_clearance_m']!=round(minimum,3) or
                metric['maximum_lane_center_deviation_m']!=round(max_offset,3) or
                metric['island_visible_frames']!=visible or
                metric['entry_visible_frames']!=entry_visible or
                metric['legal_verdict'] is not None or metric['delivery_ready']):
            raise ValueError('Independent rotary saved metric differs')
        if measure(folder,hashes)!=metric:
            raise ValueError('Rotary saved processor replay differs')
    source=HERE/'saved-fixtures'/'reference';replayed=[]
    for mutation in mutations:
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
            hashes={name:sha(folder/name) for name in FILES}
            if mutation=='wrong_expected_hash':hashes['native-observed.jsonl']='0'*64
            try:measure(folder,hashes if mutation=='wrong_expected_hash' else None)
            except (ValueError,TypeError):replayed.append(mutation)
            else:raise ValueError('Independent rotary saved negative accepted')
    if seen!={'reference','contrast'} or checked!=480:
        raise ValueError('Rotary saved coverage incomplete')
    receipt={'format':'c234827-independent-saved-audit-v1',
        'proof_sha256':sha(proof_path),'saved_rows_recomputed':checked,
        'negative_controls_replayed':replayed,
        'original_native_observed':False,'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
