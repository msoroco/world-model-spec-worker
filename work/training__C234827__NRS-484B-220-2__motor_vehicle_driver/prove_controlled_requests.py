"""Prove authored rotary reference/contrast request pairing only."""
import hashlib
import json
from pathlib import Path

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]


def validate_pair(first,second):
    if len(first)!=240 or len(second)!=240:
        raise ValueError('Rotary pair frame coverage differs')
    for i,(a,b) in enumerate(zip(first,second)):
        if (a['frame']!=i or b['frame']!=i or a['time_s']!=b['time_s'] or
                a['ego_speed_mps']!=b['ego_speed_mps'] or
                a['lane_id']!=b['lane_id'] or
                a['requested_radius_m']!=b['requested_radius_m'] or
                a['island_center_xy_m']!=b['island_center_xy_m'] or
                a['candidate_id']!=b['candidate_id'] or
                a['case']!='reference' or b['case']!='contrast' or
                abs(a['ego_x_m']-b['ego_x_m'])>1e-5 or
                abs(a['ego_y_m']+b['ego_y_m'])>1e-5 or
                abs(((a['ego_heading_deg']+b['ego_heading_deg'])%360))>1e-4 and
                abs(((a['ego_heading_deg']+b['ego_heading_deg'])%360)-360)>1e-4):
            raise ValueError('Rotary fixed controls or mirrored passage differ')
    return {'frames':240,'fixed_ring_and_speed':True,
            'mirrored_lateral_position':True,
            'reference_island_side_request':'left',
            'contrast_island_side_request':'right'}


def prove():
    pairs=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        first=NATIVE/'drafts'/'reference'/candidate/'requested-tracks.jsonl'
        second=NATIVE/'drafts'/'contrast'/candidate/'requested-tracks.jsonl'
        metric=validate_pair(rows(first),rows(second))
        pairs.append({'candidate_id':candidate,'reference_sha256':sha(first),
                      'contrast_sha256':sha(second),'metric':metric})
    first=rows(NATIVE/'drafts'/'reference'/'primary'/'requested-tracks.jsonl')
    second=rows(NATIVE/'drafts'/'contrast'/'primary'/'requested-tracks.jsonl')
    negatives=[]
    for mutation in ('speed','lane','mirror_position','heading'):
        altered=[dict(row) for row in second]
        key,value={'speed':('ego_speed_mps',9),
                   'lane':('lane_id',-2),
                   'mirror_position':('ego_y_m',0),
                   'heading':('ego_heading_deg',17)}[mutation]
        altered[60][key]=value
        try:validate_pair(first,altered)
        except ValueError:negatives.append({'mutation':mutation,'rejected':True})
        else:raise AssertionError('Rotary altered pair accepted')
    proof={'format':'c234827-controlled-request-comparison-v1',
        'assignment_id':CASE.name,
        'road_sha256':sha(NATIVE/'road.xodr'),
        'island_geometry_sha256':sha(NATIVE/'island-geometry.json'),
        'construction_manifest_sha256':sha(NATIVE/'drafts'/'manifest.json'),
        'pairs':pairs,'negative_controls':negatives,
        'original_native_observed':False,'physical_island_verified':False,
        'accepted_comparison':False,'legal_verdict':None,'delivery_ready':False}
    (CASE/'controlled-request-comparison.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    proof=prove();print(json.dumps({'pairs':len(proof['pairs']),
                                    'negatives':len(proof['negative_controls'])}))
