"""Independent raw-source and retained exact package audit for exception C."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from exception_c_engineering import body,overlap

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def main():
    manifest=read(HERE/'draft-exception-c-execution-manifest.json')
    index=read(HERE/'exception-c-package-durable-index.json')
    assert index['source_kind']=='synthetic_cpu_fixture' and index['accepted'] is False
    assert len(index['receipts'])==8
    pairs={}
    for response in ('avoid','no_conflict'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            label=response+'-'+candidate
            proof=read(HERE/('exception-c-package-'+label+'.json'))
            assert proof['passed'] and proof['accepted'] is False and proof['selected'] is False
            assert proof['original_native_capture_executed'] is False
            assert proof['manifest_sha256']==sha(HERE/'draft-exception-c-execution-manifest.json')
            entry=next(e for e in manifest['cases'] if e['case_id']==proof['case_id'])
            ref=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            assert proof['construction_sha256']==ref['construction_sha256']==sha(HERE/ref['construction'])
            folder=HERE/'draft-exception-c-exact-cases'/('exception_c_'+response)/candidate/'package-proof'
            durable=read(folder/'durable-receipt.json')
            assert index['receipts'][label]==sha(folder/'durable-receipt.json')
            assert all(sha(folder/name)==digest for name,digest in durable['files'].items())
            source=HERE/'draft-exception-c-cases'/response/candidate/'source-rows.jsonl'
            assert durable['source_rows_sha256']==sha(source)
            receipt=read(folder/'compatibility.json')
            assert receipt['passed'] and receipt['construction_sha256']==proof['construction_sha256']
            assert proof['positive_receipt_sha256']==sha(folder/'compatibility.json')
            assert receipt['log_sha256']==sha(folder/'analysis.log')
            assert set(receipt['checks'])>={'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'}
            assert all(read(folder/name)['passed'] for name in ('source-0.json','source-1.json',
                'source-2.json','source-3.json','final-decode.json'))
            report=read(folder/'analysis-report.json');result=read(folder/'result.json')
            assert report['accepted'] is False and result['accepted'] is False
            assert report['source_scope']=='synthetic_cpu_fixture'
            assert report['video_frames']=={name+'.mkv':480 for name in
                ('overview','approach','reference_corner','driver_reference')}
            rows=[json.loads(line) for line in source.read_text().splitlines()]
            assert len(rows)==480
            assert read(folder/'exception-c-source-manifest.json')['samples_sha256']==sha(source)
            assert all(row['native_frame']==1000+i and row['time_s']==round(i/20,2)
                for i,row in enumerate(rows))
            active=[i for i,r in enumerate(rows) if r['conflict_actor_active']]
            actual=[i for i,r in enumerate(rows) if r['conflict_actor_active'] and
                overlap(r['ego_body_xy'],r['conflict_actor_body_xy'])>.001]
            straight=[i for i,r in enumerate(rows) if r['conflict_actor_active'] and
                overlap(body(r['ego_center_xy'][0],-1.5),r['conflict_actor_body_xy'])>.001]
            bike=[i for i,r in enumerate(rows) if overlap(r['ego_body_xy'],
                [[-15,-5],[20,-5],[20,-3],[-15,-3]])>.001]
            assert len(active)==report['measurements']['active_conflict_actor_frames']
            assert len(actual)==report['measurements']['actual_collision_frames']==0
            assert len(straight)==report['measurements']['counterfactual_straight_collision_frames']
            assert len(bike)==report['measurements']['bicycle_lane_occupied_frames']
            assert bool(active)==(response=='avoid') and bool(bike)==(response=='avoid')
            assert proof['negative_exit_code']!=0 and proof['negative_log_sha256']==sha(folder/'negative.log')
            assert 'Synthetic conflict source hash differs' in (folder/'negative.log').read_text()
            pairs[response,candidate]={'active':len(active),'bike':len(bike),'triggers':proof['triggers']}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        assert pairs['avoid',candidate]['active']==71
        assert pairs['no_conflict',candidate]['active']==0
        assert pairs['no_conflict',candidate]['bike']==0
        for response in ('avoid','no_conflict'):
            trigger=pairs[response,candidate]['triggers']
            assert trigger['approach_runway_m']==(60.0 if candidate=='fallback1' else 50.0)
            assert trigger['scripted_reference_visible_fraction']==(1.0 if candidate=='fallback3' else .901408)
            assert trigger['original_camera_pixels_verified'] is False
            if response=='avoid':assert trigger['diversion_lead_frames']==(34 if candidate=='fallback2' else 24)
    summary={'format':'c10052-exception-c-package-independent-audit-v1','passed':True,
        'positive_package_receipts':8,'changed_source_negatives':8,
        'controlled_avoid_no_conflict_pairs':4,
        'scope':'unselected synthetic saved package processing',
        'original_native_capture_executed':False,'accepted':False}
    (HERE/'exception-c-package-audit-v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':main()
