"""Retain labelled synthetic saved rows for each connected exit request."""
import json
import math
from pathlib import Path
from measure_exit_saved import sha, rows

HERE=Path(__file__).resolve().parent

def build():
    for witness in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            source=HERE/'exit-network-drafts'/witness/candidate
            track=source/'requested-tracks.jsonl'
            folder=HERE/'exit-saved-fixtures'/witness/candidate
            folder.mkdir(parents=True,exist_ok=True)
            observed=[];frames=[]
            for row in rows(track):
                heading=math.radians(row['ego_heading_deg'])
                tangent=(math.cos(heading),math.sin(heading))
                normal=(-tangent[1],tangent[0])
                body=[]
                for along,across in ((-1,-.5),(-1,.5),(1,-.5),(1,.5)):
                    body.append([round(row['ego_x_m']+along*tangent[0]+across*normal[0],6),
                                 round(row['ego_y_m']+along*tangent[1]+across*normal[1],6)])
                observed.append({'frame':row['frame'],'native_frame':1000+row['frame'],
                                 'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                                 'witness':witness,'candidate_id':candidate,
                                 'road_id':row['road_id'],'phase':row['phase'],
                                 'lane_id':row['lane_id'],'ego_x_m':row['ego_x_m'],
                                 'ego_y_m':row['ego_y_m'],'ego_speed_mps':row['ego_speed_mps'],
                                 'ego_body_xy_m':body,'actual_exit_observed':False})
                frames.append({'frame':row['frame'],'camera_frame':1000+row['frame'],
                               'time_s':row['time_s'],'source_kind':'synthetic_cpu',
                               'left_lane_visible':True})
            (folder/'native-observed.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in observed))
            (folder/'camera-frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
            readback={'source_kind':'synthetic_cpu','road_sha256':sha(HERE/'left-exit-road.xodr'),
                      'request_sha256':sha(track),'physical_roundabout_verified':False}
            (folder/'lane-readback.json').write_text(json.dumps(readback,indent=2)+'\n')

if __name__=='__main__':build();print(json.dumps({'fixtures':8}))
