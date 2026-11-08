"""Independent raw-source audit for the traffic-conflict control pair."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_c_engineering import NAMES,body,measure,policy

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def hit(a,b):
    ax=[p[0] for p in a];ay=[p[1] for p in a]
    bx=[p[0] for p in b];by=[p[1] for p in b]
    return min(max(ax),max(bx))-max(min(ax),min(bx))>.001 and min(max(ay),max(by))-max(min(ay),min(by))>.001

def main():
    root=HERE/'draft-exception-c-cases';pairs=[]
    summary=read(HERE/'exception-c-source-summary.json')
    assert summary['positive_source_receipts']==8 and summary['controlled_pairs']==4
    assert summary['legal_exception_verified'] is False
    for candidate in NAMES:
        pair={}
        for response in ('avoid','no_conflict'):
            folder=root/response/candidate
            receipt=read(folder/'receipt.json')
            for name,key in (('construction.json','construction_sha256'),
                             ('source-rows.jsonl','source_sha256'),
                             ('measurement.json','measurement_sha256'),
                             ('trigger-measurement.json','trigger_sha256')):
                assert sha(folder/name)==receipt[key]
            p=read(folder/'construction.json')
            assert p==policy(response,candidate)
            source=[json.loads(line) for line in (folder/'source-rows.jsonl').read_text().splitlines()]
            result=read(folder/'measurement.json');trigger=read(folder/'trigger-measurement.json')
            assert len(source)==480
            assert all(row['native_frame']==1000+i and row['time_s']==round(i/20,2)
                       for i,row in enumerate(source))
            assert all(row['synthetic_diagnostic'] is True for row in source)
            actor=[i for i,row in enumerate(source) if row['conflict_actor_active']]
            actual=[i for i in actor if hit(source[i]['ego_body_xy'],source[i]['conflict_actor_body_xy'])]
            straight=[i for i in actor if hit(body(source[i]['ego_center_xy'][0],-1.5),
                                              source[i]['conflict_actor_body_xy'])]
            bike=[i for i,row in enumerate(source) if hit(row['ego_body_xy'],
                [[-15,-5],[20,-5],[20,-3],[-15,-3]])]
            assert len(actor)==result['active_conflict_actor_frames']
            assert len(actual)==result['actual_collision_frames']==0
            assert len(straight)==result['counterfactual_straight_collision_frames']
            assert len(bike)==result['bicycle_lane_occupied_frames']
            assert result['synthetic_avoidance_geometry'] is True
            assert result['accepted'] is False and result['legal_exception_verified'] is False
            changed=[dict(row) for row in source];changed[200]['native_frame']+=1
            try:measure(changed,p)
            except ValueError as exc:assert str(exc)==receipt['frame_mutation_rejected']
            else:raise AssertionError('Changed frame accepted')
            if response=='avoid':
                assert len(actor)==71 and len(straight)>0 and len(bike)>0
                absent=[dict(row) for row in source]
                for row in absent:
                    row['conflict_actor_id']=None;row['conflict_actor_body_xy']=[]
                    row['conflict_actor_active']=False
            else:
                assert not actor and not bike
                absent=[dict(row) for row in source]
                for row in absent[165:236]:
                    row['conflict_actor_id']=221
                    row['conflict_actor_body_xy']=body(0,-1.5,4.6,1.8)
                    row['conflict_actor_active']=True
            negative=measure(absent,p)
            assert negative==receipt['causal_negative']
            assert negative['synthetic_avoidance_geometry'] is False
            pair[response]={'rows':source,'measurement':result,'triggers':trigger}
        a=pair['avoid'];n=pair['no_conflict']
        assert all(x['ego_center_xy'][0]==y['ego_center_xy'][0] and
                   x['scripted_reference_visible']==y['scripted_reference_visible']
                   for x,y in zip(a['rows'],n['rows']))
        assert a['measurement']['bicycle_lane_occupied_frames']>0
        assert n['measurement']['bicycle_lane_occupied_frames']==0
        t=a['triggers']
        assert t['approach_runway_m']==(60 if candidate=='fallback1' else 50)
        assert t['diversion_lead_frames']==(34 if candidate=='fallback2' else 24)
        assert t['scripted_reference_visible_fraction']==(1.0 if candidate=='fallback3' else .901408)
        assert t['original_camera_pixels_verified'] is False
        pairs.append({'candidate_id':candidate,'straight_collision_frames':
            a['measurement']['counterfactual_straight_collision_frames'],
            'avoidance_lane_frames':a['measurement']['bicycle_lane_occupied_frames'],
            'control_lane_frames':0})
    proof={'format':'c10052-exception-c-independent-audit-v1','passed':True,
           'positive_sources':8,'causal_negatives':8,'changed_frame_negatives':8,
           'controlled_pairs':pairs,'original_native_verified':False,
           'legal_exception_verified':False,'accepted':False}
    (HERE/'exception-c-independent-audit.json').write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'positive_sources':8,'controlled_pairs':4}))
if __name__=='__main__':main()
