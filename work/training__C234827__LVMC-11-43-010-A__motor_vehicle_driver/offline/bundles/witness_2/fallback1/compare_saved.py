"""Compare the two source-bound synthetic passages under controlled conditions."""
import hashlib
import json
from pathlib import Path

from measure_saved import measure, rows

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def compare(first=None,second=None):
    first=Path(first or HERE/'saved-fixtures'/'witness_1')
    second=Path(second or HERE/'saved-fixtures'/'witness_2')
    a=measure(first);b=measure(second)
    if (a['source_kind']!='synthetic_cpu' or b['source_kind']!='synthetic_cpu' or
        a['witness']!='witness_1' or b['witness']!='witness_2' or
        a['frames']!=240 or b['frames']!=240 or
        a['signed_angular_progress_rad']<=0 or b['signed_angular_progress_rad']>=0 or
        a['rotation_frame_counts']['counterclockwise']!=240 or
        b['rotation_frame_counts']['clockwise']!=240 or
        not a['continuous_requested_rotation'] or not b['continuous_requested_rotation']):
        raise ValueError('Saved LVMC directional contrast absent')
    ao=rows(first/'native-observed.jsonl');bo=rows(second/'native-observed.jsonl')
    af=rows(first/'roundabout-frames.jsonl');bf=rows(second/'roundabout-frames.jsonl')
    if sha(first/'roundabout-readback.json')!=sha(second/'roundabout-readback.json'):
        raise ValueError('Roundabout map/readback differs')
    for i,(x,y,f,g) in enumerate(zip(ao,bo,af,bf)):
        for key in ('frame','time_s','lane_id','ego_speed_mps','source_kind'):
            if x[key]!=y[key]:raise ValueError(f'Controlled {key} differs at {i}')
        for key in ('frame','time_s','roundabout_visible'):
            if f[key]!=g[key]:raise ValueError(f'Controlled camera {key} differs at {i}')
        if (abs(x['ego_x_m']-y['ego_x_m'])>1e-6 or
            abs(x['ego_y_m']+y['ego_y_m'])>1e-6):
            raise ValueError(f'Mirrored passage position differs at {i}')
    if (abs(a['signed_angular_progress_rad']+b['signed_angular_progress_rad'])>.0001 or
        a['occupied_authored_ring_frames']!=b['occupied_authored_ring_frames'] or
        a['minimum_body_island_clearance_m']!=b['minimum_body_island_clearance_m']):
        raise ValueError('Controlled measured passage differs')
    return {'format':'c234827-lvmc-saved-comparison-v1',
            'source_hashes':{'witness_1':a['source_hashes'],'witness_2':b['source_hashes']},
            'controlled_fields':['map_readback','frame','time_s','lane_id',
                                 'ego_speed_mps','roundabout_visible','mirrored_xy'],
            'measured_signed_progress_rad':[a['signed_angular_progress_rad'],b['signed_angular_progress_rad']],
            'rotation_frames':[a['rotation_frame_counts']['counterclockwise'],
                               b['rotation_frame_counts']['clockwise']],
            'occupied_authored_ring_frames':[a['occupied_authored_ring_frames'],
                                             b['occupied_authored_ring_frames']],
            'physical_roundabout_verified':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    result=compare()
    (HERE/'saved-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
