"""Independent retained package and raw assignment/body audit for exception D."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def overlap(body):
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return max(0,min(max(xs),20)-max(min(xs),-15))*max(0,min(max(ys),-3)-max(min(ys),-5))

def main():
    manifest=read(HERE/'draft-exception-d-execution-manifest.json')
    index=read(HERE/'exception-d-package-durable-index.json')
    assert index['source_kind']=='synthetic_cpu_fixture' and index['accepted'] is False
    assert len(index['receipts'])==8
    pairs={}
    for response in ('duty','routine'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            label=response+'-'+candidate
            proof=read(HERE/('exception-d-package-'+label+'.json'))
            assert proof['passed'] and proof['accepted'] is False and proof['selected'] is False
            assert proof['original_native_capture_executed'] is False
            assert proof['manifest_sha256']==sha(HERE/'draft-exception-d-execution-manifest.json')
            entry=next(e for e in manifest['cases'] if e['case_id']==proof['case_id'])
            ref=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            assert proof['construction_sha256']==ref['construction_sha256']==sha(HERE/ref['construction'])
            folder=HERE/'draft-exception-d-exact-cases'/('exception_d_'+response)/candidate/'package-proof'
            durable=read(folder/'durable-receipt.json')
            assert index['receipts'][label]==sha(folder/'durable-receipt.json')
            assert all(sha(folder/name)==digest for name,digest in durable['files'].items())
            source_folder=HERE/'draft-exception-d-cases'/response/candidate
            source=source_folder/'source-rows.jsonl'
            packet=read(source_folder/'duty-assignment.json')
            assert durable['source_rows_sha256']==sha(source)
            assert durable['fixture_duty_assignment_sha256']==sha(source_folder/'duty-assignment.json')
            assert sha(folder/'duty-assignment.json')==sha(source_folder/'duty-assignment.json')
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
            source_manifest=read(folder/'exception-d-source-manifest.json')
            assert source_manifest['samples_sha256']==sha(source)
            assert source_manifest['duty_assignment_sha256']==sha(source_folder/'duty-assignment.json')
            rows=[json.loads(line) for line in source.read_text().splitlines()]
            assert len(rows)==480
            assert all(r['native_frame']==3000+i and r['time_s']==round(i/20,2) for i,r in enumerate(rows))
            assert packet['issuer']=='synthetic_public_works_dispatch'
            assert packet['assignment_id']=='fixture-duty-001'
            assert packet['active'] is (response=='duty')
            assert packet['task']==('bicycle_facility_surface_inspection' if response=='duty' else 'none')
            assert (packet['authorized_vehicle_id'],packet['authorized_operator_id'])==(
                ('fixture-service-vehicle-17','fixture-operator-04') if response=='duty' else (None,None))
            assert (packet['start_frame'],packet['end_frame'])==(
                (100,240) if response=='duty' else (None,None))
            active=sum(r['duty_active'] for r in rows)
            bike=sum(overlap(r['ego_body_xy'])>.001 for r in rows)
            joined=sum(r['duty_active'] and overlap(r['ego_body_xy'])>.001 for r in rows)
            assert all(r['assignment_id']==(packet['assignment_id'] if r['duty_active'] else None) for r in rows)
            assert all((r['vehicle_id'],r['operator_id'])==
                ('fixture-service-vehicle-17','fixture-operator-04') for r in rows)
            assert (active,bike,joined)==((140,70,70) if response=='duty' else (0,0,0))
            assert (report['measurements']['duty_active_frames'],
                report['measurements']['bicycle_lane_occupied_frames'],
                report['measurements']['duty_occupied_frames'])==(active,bike,joined)
            assert proof['negative_exit_code']!=0 and proof['negative_log_sha256']==sha(folder/'negative.log')
            assert 'Duty source scope or bytes changed' in (folder/'negative.log').read_text()
            pairs[response,candidate]={'rows':rows,'triggers':proof['triggers']}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        a=pairs['duty',candidate]['rows'];b=pairs['routine',candidate]['rows']
        assert all(x['native_frame']==y['native_frame'] and x['time_s']==y['time_s']
            and x['ego_center_xy'][0]==y['ego_center_xy'][0]
            and x['scripted_reference_visible']==y['scripted_reference_visible']
            for x,y in zip(a,b))
        for response in ('duty','routine'):
            trigger=pairs[response,candidate]['triggers']
            assert trigger['duty_observation_frames']==(
                0 if response=='routine' else (120 if candidate=='fallback1' else 80))
            assert trigger['response_lead_frames']==(35 if candidate=='fallback2' else 20)
            assert trigger['scripted_reference_visible_fraction']==(
                1.0 if candidate=='fallback3' else .887324)
            assert trigger['original_camera_pixels_verified'] is False
    summary={'format':'c10052-exception-d-package-independent-audit-v1','passed':True,
        'positive_package_receipts':8,'changed_source_negatives':8,
        'controlled_duty_routine_pairs':4,
        'scope':'unselected synthetic saved package processing',
        'original_native_capture_executed':False,'accepted':False}
    (HERE/'exception-d-package-audit-v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':main()
