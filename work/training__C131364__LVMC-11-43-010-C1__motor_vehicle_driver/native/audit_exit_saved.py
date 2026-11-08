"""Independently recompute synthetic connected saved phase and lane coverage."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]

def audit():
    entries=[];total=0;exit_paths=0
    road=HERE/'left-exit-road.xodr'
    for witness,lane,radius in (('witness_1',-1,23.75),('witness_2',-2,27.25)):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            request=HERE/'exit-network-drafts'/witness/candidate
            saved=HERE/'exit-saved-fixtures'/witness/candidate
            config=json.loads((request/'config.json').read_text())
            readback=json.loads((saved/'lane-readback.json').read_text())
            track=request/'requested-tracks.jsonl'
            if (config['road_sha256']!=sha(road) or config['tracks_sha256']!=sha(track) or
                readback['road_sha256']!=sha(road) or readback['request_sha256']!=sha(track) or
                readback['source_kind']!='synthetic_cpu' or readback['physical_roundabout_verified']):
                raise ValueError('C131364 connected saved audit source differs')
            requests=rows(track);observed=rows(saved/'native-observed.jsonl');camera=rows(saved/'camera-frames.jsonl')
            if not(len(requests)==len(observed)==len(camera)==240):
                raise ValueError('C131364 connected saved audit length differs')
            counts={'entry':0,'circulation':0,'exit':0};contained=0
            for i,(req,obs,frame) in enumerate(zip(requests,observed,camera)):
                if (req['frame']!=i or obs['frame']!=i or frame['frame']!=i or
                    obs['native_frame']!=frame['camera_frame'] or
                    obs['time_s']!=req['time_s'] or frame['time_s']!=req['time_s'] or
                    obs['witness']!=witness or obs['candidate_id']!=candidate or
                    obs['road_id']!=req['road_id'] or obs['phase']!=req['phase'] or
                    obs['lane_id']!=lane or obs['actual_exit_observed'] or
                    abs(obs['ego_x_m']-req['ego_x_m'])>1e-6 or
                    abs(obs['ego_y_m']-req['ego_y_m'])>1e-6):
                    raise ValueError(f'C131364 connected saved audit row {i} differs')
                counts[obs['phase']]+=1
                if len(obs.get('ego_body_xy_m',[]))!=4:
                    raise ValueError('C131364 connected saved body coverage differs')
                heading=math.radians(req['ego_heading_deg'])
                forward=(math.cos(heading),math.sin(heading))
                left=(-forward[1],forward[0])
                for point,(along,across) in zip(obs['ego_body_xy_m'],
                                                 ((-1,-.5),(-1,.5),(1,-.5),(1,.5))):
                    expected=(req['ego_x_m']+along*forward[0]+across*left[0],
                              req['ego_y_m']+along*forward[1]+across*left[1])
                    if math.hypot(point[0]-expected[0],point[1]-expected[1])>1e-5:
                        raise ValueError('C131364 connected saved body differs')
                if obs['phase']=='circulation':
                    low,high=(22,25.5) if lane==-1 else (25.5,29)
                    if all(low<=math.hypot(*point)<=high for point in obs['ego_body_xy_m']):contained+=1
            if candidate=='fallback3':
                if counts['circulation'] or counts['exit']:raise ValueError('C131364 stop route advanced')
            elif not all(counts.values()):raise ValueError('C131364 left-exit phase absent')
            total+=240;exit_paths+=bool(counts['exit'])
            entries.append({'witness':witness,'candidate_id':candidate,
                            'phase_frames':counts,'full_body_circulation_lane_frames':contained,
                            'request_sha256':sha(track),'observed_sha256':sha(saved/'native-observed.jsonl')})
    if total!=1920 or exit_paths!=6:raise ValueError('C131364 connected saved audit coverage differs')
    result={'format':'c131364-independent-connected-saved-audit-v1','entries':entries,
            'saved_rows_recomputed':total,'synthetic_exit_paths':exit_paths,
            'original_native_observed':False,'physical_roundabout_verified':False,
            'actual_left_exit_observed':False,'delivery_ready':False}
    (HERE/'exit-saved-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'rows':audit()['saved_rows_recomputed']}))
