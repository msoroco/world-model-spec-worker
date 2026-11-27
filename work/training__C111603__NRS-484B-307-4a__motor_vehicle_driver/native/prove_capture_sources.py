"""CPU-test the original-source projection and missing-source rejection."""

import json
import os
from pathlib import Path
import tempfile

from capture import derive_channels


def run():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root=Path(tmp)
        context={'arrow_facing_source':'surveyed_original_head',
                 'intersection_bounds_m':[0,5,-2,2],
                 'adjacent_crosswalk_bounds_m':[1,3,1,2]}
        (root/'intersection-context.json').write_text(json.dumps(context)+'\n')
        actor={'actor_id':1,'type_id':'vehicle.tesla.model3','x_m':1.0,'y_m':0.0,
               'z_m':0.0,'yaw_deg':0.0,'speed_mps':2.0,
               'body_vertices_native_m':[[1.0,0.0,0.0]]}
        native=[];frames=[]
        for i in range(600):
            native.append({'source_kind':'original_native_fixture_not_a_capture',
                'native_frame':1000+i,'time_s':i/20,
                'actors':{'ego':actor,'pedestrian':actor,'other_traffic':actor},
                'signal':{'opendrive_id':'123','native_actor_id':7,'raw_state':'green',
                          'green_turn_arrow_alone_verified':False},
                'requested_phase':'turn_request','legal_verdict':None})
            frames.append({'native_frame':1000+i,'source_cameras':{
                'overview':1000+i,'approach':1000+i,
                'reference_corner':1000+i,'driver_reference':1000+i}})
        (root/'native.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in native))
        (root/'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
        channels=derive_channels(root)
        assert len(channels)==11
        assert all(len((root/row['reference']).read_text().splitlines())==600 for row in channels)
        first=json.loads((root/'channels'/'dev.traffic_signal.jsonl').read_text().splitlines()[0])
        assert first['value']['arrow_pixels_reviewed'] is False
        assert first['value']['native_signal']['raw_state']=='green'
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        try:derive_channels(Path(tmp))
        except FileNotFoundError:pass
        else:raise AssertionError('Missing Native source accepted')
    return {'named_original_source_projection_channels':11,'frames_per_channel':600,
            'missing_native_source_negative':True,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}


if __name__=='__main__':
    print(json.dumps(run(),sort_keys=True))
