"""Independently recompute eight synthetic saved pass and object measurements."""
import hashlib
import json
import math
from pathlib import Path

from route_fallbacks import route

CASE=Path(__file__).resolve().parents[1]
HERE=CASE/'native'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def require(ok,message):
    if not ok:raise ValueError(message)


def audit():
    proof=read(HERE/'saved-proof.json')
    contract=read(HERE/'measurement-contract.json')
    require(contract['source_law_id']=='NRS-484B-210-1' and
            contract['rate_hz']==20 and contract['frames']==240 and
            contract['legal_verdict_from_geometry_alone'] is False,
            'measurement contract')
    require(proof['positives']==8 and proof['semantic_negatives']==16 and
            len(proof['entries'])==8 and
            proof['original_native_observed'] is False and
            proof['delivery_ready'] is False,'saved proof inventory')
    by_key={};results=[]
    for witness in ('witness_1','witness_2'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle=HERE/'drafts'/witness/candidate
            saved=HERE/'saved-fixtures'/witness/candidate
            cfg=read(bundle/'config.json')
            req=rows(bundle/'requested-tracks.jsonl')
            actors=rows(saved/'native-observed.jsonl')
            cameras=rows(saved/'camera-frames.jsonl')
            back=read(saved/'readback.json')
            entry=next(x for x in proof['entries'] if x['case_id']==cfg['case_id']
                       and x['candidate_id']==candidate)
            require(len(req)==len(actors)==len(cameras)==240 and
                    back['source_kind']=='synthetic_cpu' and
                    back['observed_sha256']==sha(saved/'native-observed.jsonl') and
                    back['camera_sha256']==sha(saved/'camera-frames.jsonl') and
                    back['config_sha256']==sha(bundle/'config.json') and
                    all(entry['saved_hashes'][name]==sha(saved/name) for name in
                        ('native-observed.jsonl','camera-frames.jsonl','readback.json')),
                    'saved source binding')
            require('saved frame coverage' in entry['negative_errors'][
                'missing_camera_frame'] and
                'body corner identity' in entry['negative_errors'][
                    'changed_body_vertex'], 'semantic negatives')
            pass_frames=0;overlap_frames=0;clearance=None
            for i,(r,a,c) in enumerate(zip(req,actors,cameras)):
                require(a['frame']==c['frame']==r['frame']==i and
                        a['native_frame']==c['native_frame']==1000+i and
                        a['source_kind']==c['source_kind']=='synthetic_cpu' and
                        a['road_id']==210 and
                        a['ego_x_m']==r['ego_x_m'] and
                        a['ego_y_m']==r['ego_y_m'] and
                        a['lead_x_m']==r['lead_x_m'] and
                        a['lead_y_m']==r['lead_y_m'] and
                        not c['object_pixel_reviewed'] and
                        a['legal_verdict'] is None,
                        f'actor/frame source {i}')
                ego={(round(x,6),round(y,6)) for x,y in a['ego_body_xy_m']}
                lead={(round(x,6),round(y,6)) for x,y in a['lead_body_xy_m']}
                require(ego=={(round(a['ego_x_m']+dx,6),round(a['ego_y_m']+dy,6))
                    for dx,dy in ((-2.3,-1),(-2.3,1),(2.3,1),(2.3,-1))} and
                    lead=={(round(a['lead_x_m']+dx,6),round(a['lead_y_m']+dy,6))
                    for dx,dy in ((-2.3,-1),(-2.3,1),(2.3,1),(2.3,-1))},
                    f'original body source {i}')
                ex=[x for x,y in ego];ey=[y for x,y in ego]
                lx=[x for x,y in lead];ly=[y for x,y in lead]
                if max(ey)<min(ly) and min(ex)>max(lx) and a['ego_lane_id']==-2:
                    pass_frames+=1
                if witness=='witness_2':
                    require(a['obstruction_actor_id']==3 and
                            a['obstruction_x_m']==55 and
                            a['obstruction_y_m']==-6.8 and
                            a['obstruction_radius_m']==.2,
                            f'obstruction actor {i}')
                    dx=max(min(ex)-55,0,55-max(ex))
                    dy=max(min(ey)+6.8,0,-6.8-max(ey))
                    gap=math.hypot(dx,dy)-.2
                    clearance=gap if clearance is None else min(clearance,gap)
                    if abs(a['ego_x_m']-55)<3 and a['ego_lane_id']==-2:
                        overlap_frames+=1
                else:
                    require(a['obstruction_actor_id'] is None,'reference obstacle')
            claimed_clearance=None if clearance is None else round(clearance,6)
            routed=route(bundle,saved)
            require(entry['passing_right_geometry_frames']==pass_frames and
                    entry['min_clearance_m']==claimed_clearance and
                    routed['triggers']['fallback1']['triggered']==
                    (claimed_clearance is not None and claimed_clearance<.5) and
                    routed['triggers']['fallback2']['triggered'] and
                    routed['triggers']['fallback3']['triggered'] and
                    routed['selected_fallback'] is None and
                    routed['delivery_ready'] is False,
                    'saved measurement/router')
            by_key[witness,candidate]=(actors,pass_frames,overlap_frames)
            results.append({'witness':witness,'candidate_id':candidate,
                            'passing_right_geometry_frames':pass_frames,
                            'object_overlap_frames':overlap_frames,
                            'min_clearance_m':claimed_clearance})
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=by_key['witness_1',candidate][0]
        b=by_key['witness_2',candidate][0]
        fixed=('frame','native_frame','time_s','road_id','ego_x_m','ego_y_m',
               'ego_body_xy_m','ego_lane_id','lead_x_m','lead_y_m',
               'lead_body_xy_m','lead_lane_id')
        require(all(all(x[k]==y[k] for k in fixed) for x,y in zip(a,b)),
                'saved controlled-pair invariants')
    receipt={'format':'c146314-independent-saved-audit-v1',
             'rows_recomputed':1920,'positives':8,'semantic_negatives':16,
             'results':results,'original_native_observed':False,
             'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    x=audit()
    print(json.dumps({'rows_recomputed':x['rows_recomputed'],
                      'positives':x['positives'],
                      'semantic_negatives':x['semantic_negatives']}))
