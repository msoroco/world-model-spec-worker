"""Measure source-bound circulating lane use; require an actual exit separately."""
import hashlib
import json
import math
from pathlib import Path

FILES=('native-observed.jsonl','lane-readback.json','camera-frames.jsonl')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]

def measure(folder,expected_hashes=None):
    folder=Path(folder)
    hashes={name:sha(folder/name) for name in FILES}
    if expected_hashes is not None and hashes!=expected_hashes:
        raise ValueError('C131364 saved source hash differs')
    observed=rows(folder/'native-observed.jsonl')
    frames=rows(folder/'camera-frames.jsonl')
    readback=json.loads((folder/'lane-readback.json').read_text())
    if len(observed)!=240 or len(frames)!=240:
        raise ValueError('C131364 saved frame count differs')
    witness=observed[0].get('witness')
    kind=observed[0].get('source_kind')
    lane,radius=(-1,23.75) if witness=='witness_1' else (-2,27.25)
    if (witness not in ('witness_1','witness_2') or
        kind not in ('synthetic_cpu','original_native') or
        readback.get('source_kind')!=kind or
        readback.get('road_sha256') is None or
        readback.get('driving_lane_ids')!=[-2,-1] or
        readback.get('left_lane_id')!=-1 or
        readback.get('right_lane_id')!=-2 or
        readback.get('physical_roundabout_verified') is not False or
        readback.get('exit_connector_verified') is not False):
        raise ValueError('C131364 saved lane readback differs')
    if kind=='original_native' and (not readback.get('native_map_sha256') or
        readback.get('review_provenance')!='human_frame_review'):
        raise ValueError('C131364 original map or human review absent')
    previous=None;occupied=0;visible=0;entry_visible=0;max_deviation=0.0
    for i,(row,frame) in enumerate(zip(observed,frames)):
        if (row.get('frame')!=i or frame.get('frame')!=i or
            abs(row.get('time_s',-1)-(i+1)/20)>1e-6 or
            frame.get('time_s')!=row['time_s'] or
            row.get('witness')!=witness or row.get('source_kind')!=kind or
            row.get('lane_id')!=lane or
            frame.get('camera_frame')!=row.get('native_frame') or
            frame.get('source_kind')!=kind or
            type(frame.get('left_lane_visible')) is not bool or
            row.get('actual_exit_observed') is not False):
            raise ValueError(f'C131364 saved join differs at {i}')
        x,y=row['ego_x_m'],row['ego_y_m']
        radial=math.hypot(x,y)
        deviation=abs(radial-radius)
        if deviation>.5:raise ValueError('C131364 claimed lane center differs')
        max_deviation=max(max_deviation,deviation)
        if previous is not None:
            px,py=previous
            distance=math.hypot(x-px,y-py)*20
            if abs(distance-row['ego_speed_mps'])>.4:
                raise ValueError('C131364 speed and displacement differ')
        previous=(x,y)
        body=row.get('ego_body_xy_m')
        if not isinstance(body,list) or len(body)!=4:
            raise ValueError('C131364 body vertices missing')
        lower,upper=(22,25.5) if lane==-1 else (25.5,29)
        if all(lower<=math.hypot(*point)<=upper for point in body):occupied+=1
        if frame['left_lane_visible']:
            visible+=1
            if i<40:entry_visible+=1
    return {'format':'c131364-saved-lane-measurement-v1',
            'witness':witness,'source_kind':kind,'source_hashes':hashes,
            'frames':240,'requested_lane_id':lane,
            'full_body_requested_lane_frames':occupied,
            'maximum_lane_center_deviation_m':round(max_deviation,3),
            'left_lane_visible_frames':visible,
            'entry_visible_frames':entry_visible,
            'actual_left_exit_observed':False,'roundabout_verified':False,
            'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('folder',type=Path)
    args=parser.parse_args();print(json.dumps(measure(args.folder),indent=2))
