"""Independent source, geometry, saved-frame and controlled-pair audit."""
import json
import math
from pathlib import Path

from build import CASE, CASES, FRAMES, HERE, POLICIES, SOURCE, SOURCE_SHA, sha, put


def audit():
    source=json.loads(SOURCE.read_text())
    if sha(SOURCE)!=SOURCE_SHA or source['law_record']['text']!=json.loads((CASE/'case-plan.json').read_text())['source_law_text']:
        raise ValueError('Statutory source changed')
    if 'business district' not in source['law_record']['text'] or \
            'except at an intersection or on a divided highway' not in source['law_record']['text']:
        raise ValueError('Statutory branch text missing')
    joined=0
    for candidate in POLICIES:
        pair=[]
        for suffix,center in CASES.items():
            bundle=HERE/'drafts'/suffix/candidate
            cfg=json.loads((bundle/'config.json').read_text())
            requests=[json.loads(line) for line in (bundle/'requested-tracks.jsonl').read_text().splitlines()]
            raw=json.loads((HERE/'synthetic'/suffix/candidate/'raw.json').read_text())
            saved=json.loads((HERE/'synthetic'/suffix/candidate/'saved.json').read_text())
            if len(requests)!=FRAMES or len(raw['rows'])!=FRAMES or saved['frames_joined']!=FRAMES or \
                    saved['raw_sha256']!=sha(HERE/'synthetic'/suffix/candidate/'raw.json') or \
                    cfg['requested_turn_center_x_m']!=center or cfg['status']!='unselected_native_request' or \
                    saved['turn_center_x_m']!=center or saved['authored_at_intersection']!=(-20<=center<=20) or \
                    saved['district_designation_verified'] or saved['intersection_exception_legally_verified']:
                raise ValueError('Source-bound case or saved measurement mismatch')
            crossing=[]
            for frame,(request,observation) in enumerate(zip(requests,raw['rows'])):
                if request['frame']!=frame or observation['frame']!=frame or observation['video_frame']!=frame or \
                        observation['request_frame']!=frame or abs(observation['time_s']-frame/20)>1e-9 or \
                        observation['requested_phase']!=request['requested_phase'] or \
                        observation['ego']['center_xyz_m']!=request['requested_ego_xyz_m'] or \
                        abs(observation['ego']['heading_rad']-request['requested_heading_rad'])>1e-9 or \
                        observation['ego']['actor_id']!=10 or observation['ego']['blueprint']!=cfg['ego_blueprint']:
                    raise ValueError('Independent actor/video/request join mismatch')
                if request['requested_phase']=='u_turn' and observation['ego']['center_xyz_m'][1]>=0:
                    crossing.append(frame)
                joined+=1
            if not crossing or saved['centerline_crossing_frame']!=crossing[0] or \
                    abs(saved['centerline_crossing_x_m']-(center+6.0))>.05 or \
                    abs(saved['observed_heading_reversal_rad']-math.pi)>1e-5:
                raise ValueError('Independent centerline or heading measurement mismatch')
            pair.append((bundle,cfg,saved))
        first,second=pair
        if (first[0]/'district-crossroads.xodr').read_bytes()!=(second[0]/'district-crossroads.xodr').read_bytes() or \
                first[1]['camera_policy']!=second[1]['camera_policy'] or \
                first[1]['requested_approach_speed_mps']!=second[1]['requested_approach_speed_mps'] or \
                first[1]['pre_turn_dwell_s']!=second[1]['pre_turn_dwell_s'] or \
                second[2]['centerline_crossing_x_m']-first[2]['centerline_crossing_x_m']!=45:
            raise ValueError('Controlled pair changed fixed conditions')
    result={'format':'c111662-4033-independent-audit-v1','candidates':8,'controlled_pairs':4,
            'joined_rows':joined,'authored_away_center_x_m':-45,'authored_intersection_center_x_m':0,
            'business_district_verified':False,'original_native_observed':False,'delivery_ready':False}
    put(HERE/'independent-audit.json',result)
    return result


if __name__=='__main__':print(json.dumps(audit()))
