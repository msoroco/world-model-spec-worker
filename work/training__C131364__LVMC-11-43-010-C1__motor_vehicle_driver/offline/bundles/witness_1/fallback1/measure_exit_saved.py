"""Process source-bound saved entry, circulating, and exit phase observations."""
import hashlib
import json
import math
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path): return [json.loads(line) for line in Path(path).read_text().splitlines()]

def measure(bundle):
    bundle=Path(bundle)
    config=json.loads((bundle/'connected-config.json').read_text())
    track=bundle/'connected-requested-tracks.jsonl'
    road=bundle/'connected-road.xodr'
    observed_path=bundle/'connected-saved'/'native-observed.jsonl'
    camera_path=bundle/'connected-saved'/'camera-frames.jsonl'
    readback=json.loads((bundle/'connected-saved'/'lane-readback.json').read_text())
    if (config['tracks_sha256']!=sha(track) or config['road_sha256']!=sha(road) or
        readback.get('road_sha256')!=sha(road) or
        readback.get('request_sha256')!=sha(track) or
        readback.get('source_kind') not in ('synthetic_cpu','original_native') or
        readback.get('physical_roundabout_verified') is not False):
        raise ValueError('C131364 saved connected provenance differs')
    if readback['source_kind']=='original_native' and (not readback.get('native_map_sha256') or
        readback.get('review_provenance')!='human_frame_review'):
        raise ValueError('C131364 original connected readback lacks review')
    requests=rows(track);observed=rows(observed_path);camera=rows(camera_path)
    if len(requests)!=240 or len(observed)!=240 or len(camera)!=240:
        raise ValueError('C131364 connected saved frame count differs')
    phase_counts={'entry':0,'circulation':0,'exit':0}
    body_contained=0;visible=0;previous=None
    for i,(request,row,frame) in enumerate(zip(requests,observed,camera)):
        if (request.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=frame.get('camera_frame') or
            row.get('time_s')!=request.get('time_s') or frame.get('time_s')!=row.get('time_s') or
            row.get('source_kind')!=readback['source_kind'] or frame.get('source_kind')!=readback['source_kind'] or
            row.get('witness')!=request.get('witness') or row.get('candidate_id')!=request.get('candidate_id') or
            row.get('phase')!=request.get('phase') or row.get('road_id')!=request.get('road_id') or
            row.get('lane_id')!=config['requested_lane_id'] or
            row.get('actual_exit_observed') is not False or
            type(frame.get('left_lane_visible')) is not bool):
            raise ValueError(f'C131364 connected saved join differs at {i}')
        x,y=row['ego_x_m'],row['ego_y_m']
        if abs(x-request['ego_x_m'])>.01 or abs(y-request['ego_y_m'])>.01:
            raise ValueError('C131364 connected saved route differs')
        body=row.get('ego_body_xy_m')
        if not isinstance(body,list) or len(body)!=4 or any(not isinstance(point,list) or len(point)!=2 for point in body):
            raise ValueError('C131364 connected saved body absent')
        if previous is not None:
            measured_speed=20*math.hypot(x-previous[0],y-previous[1])
            if abs(measured_speed-row['ego_speed_mps'])>.5:
                raise ValueError('C131364 connected saved speed differs')
        previous=(x,y)
        phase=row['phase'];phase_counts[phase]+=1
        if phase=='circulation':
            lower,upper=(22,25.5) if row['lane_id']==-1 else (25.5,29)
            if all(lower<=math.hypot(*point)<=upper for point in body):body_contained+=1
        if frame['left_lane_visible']:visible+=1
    if config['candidate_id']=='fallback3':
        if phase_counts['circulation'] or phase_counts['exit']:raise ValueError('C131364 stop fallback passed entry')
    elif not all(phase_counts.values()):
        raise ValueError('C131364 connected saved route lacks exit phase')
    return {'format':'c131364-connected-saved-measurement-v1',
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'source_kind':readback['source_kind'],
            'source_hashes':{'request':sha(track),'road':sha(road),
                             'observed':sha(observed_path),'camera':sha(camera_path)},
            'phase_frames':phase_counts,'full_body_circulation_lane_frames':body_contained,
            'left_lane_visible_frames':visible,'actual_left_exit_observed':False,
            'physical_roundabout_verified':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    print(json.dumps(measure(parser.parse_args().bundle)))
