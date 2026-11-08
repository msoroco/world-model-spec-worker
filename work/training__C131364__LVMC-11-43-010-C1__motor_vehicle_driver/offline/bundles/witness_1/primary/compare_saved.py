"""Compare source-bound synthetic inner and outer lane observations."""
import json
from pathlib import Path

from measure_saved import measure, rows, sha

HERE=Path(__file__).resolve().parent

def compare(first=None,second=None):
    first=Path(first or HERE/'saved-fixtures'/'witness_1')
    second=Path(second or HERE/'saved-fixtures'/'witness_2')
    a=measure(first);b=measure(second)
    if (a['source_kind']!='synthetic_cpu' or b['source_kind']!='synthetic_cpu' or
        a['witness']!='witness_1' or b['witness']!='witness_2' or
        a['requested_lane_id']!=-1 or b['requested_lane_id']!=-2 or
        a['full_body_requested_lane_frames']!=240 or
        b['full_body_requested_lane_frames']!=240 or
        a['actual_left_exit_observed'] or b['actual_left_exit_observed']):
        raise ValueError('C131364 observed lane contrast differs')
    if sha(first/'lane-readback.json')!=sha(second/'lane-readback.json'):
        raise ValueError('C131364 lane map/readback differs')
    ao=rows(first/'native-observed.jsonl');bo=rows(second/'native-observed.jsonl')
    af=rows(first/'camera-frames.jsonl');bf=rows(second/'camera-frames.jsonl')
    for i,(x,y,f,g) in enumerate(zip(ao,bo,af,bf)):
        for key in ('frame','time_s','ego_speed_mps','source_kind'):
            if x[key]!=y[key]:raise ValueError(f'C131364 controlled {key} differs at {i}')
        for key in ('frame','time_s','left_lane_visible'):
            if f[key]!=g[key]:raise ValueError(f'C131364 controlled camera differs at {i}')
    return {'format':'c131364-saved-lane-comparison-v1',
            'source_hashes':{'witness_1':a['source_hashes'],'witness_2':b['source_hashes']},
            'controlled_fields':['map_readback','frame','time_s','speed','camera_visibility'],
            'observed_lane_ids':[a['requested_lane_id'],b['requested_lane_id']],
            'full_body_lane_frames':[a['full_body_requested_lane_frames'],
                                     b['full_body_requested_lane_frames']],
            'actual_left_exit_observed':False,'legal_verdict':None,
            'delivery_ready':False}

if __name__=='__main__':
    result=compare()
    (HERE/'saved-comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
