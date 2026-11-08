"""Independent retained package and raw-row audit for clause (b)."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())

def main():
    manifest=read(HERE/'draft-exception-b-execution-manifest.json')
    index=read(HERE/'exception-b-package-durable-index.json')
    assert index['source_kind']=='synthetic_cpu_fixture' and index['accepted'] is False
    assert len(index['receipts'])==8
    pairs={}
    for state in ('faulted','healthy'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            label=state+'-'+candidate
            proof=read(HERE/('exception-b-package-'+label+'.json'))
            assert proof['passed'] and proof['accepted'] is False and proof['selected'] is False
            assert proof['original_native_capture_executed'] is False
            assert proof['manifest_sha256']==sha(HERE/'draft-exception-b-execution-manifest.json')
            entry=next(e for e in manifest['cases'] if e['case_id']==proof['case_id'])
            ref=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            assert proof['construction_sha256']==ref['construction_sha256']==sha(HERE/ref['construction'])
            folder=HERE/'draft-exception-b-exact-cases'/('exception_b_'+state)/candidate/'package-proof'
            durable=read(folder/'durable-receipt.json')
            assert index['receipts'][label]==sha(folder/'durable-receipt.json')
            assert all(sha(folder/name)==digest for name,digest in durable['files'].items())
            source=HERE/'draft-exception-b-cases'/state/candidate/'source-rows.jsonl'
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
            samples=[json.loads(line) for line in source.read_text().splitlines()]
            assert len(samples)==480
            assert read(folder/'exception-b-source-manifest.json')['samples_sha256']==sha(source)
            assert all(r['native_frame']==2000+i and r['time_s']==round(i/20,2)
                for i,r in enumerate(samples))
            assert all(r['powertrain_readback']['drive_enabled'] is not r['fault_injection_applied']
                for r in samples)
            duration=90 if candidate=='fallback2' else 60
            test=samples[100:100+duration]
            displacement=round(test[-1]['ego_center_xy'][0]-test[0]['ego_center_xy'][0],4)
            faults=sum(r['fault_injection_applied'] for r in samples)
            assert faults==report['measurements']['fault_readback_frames']==(280 if state=='faulted' else 0)
            assert displacement==report['measurements']['propulsion_test_displacement_m']
            assert displacement==proof['propulsion_test_displacement_m']
            assert displacement==(0 if state=='faulted' else (10.68 if candidate=='fallback2' else 7.08))
            assert report['measurements']['bicycle_lane_occupied_frames_100_240']==140
            assert proof['negative_exit_code']!=0 and proof['negative_log_sha256']==sha(folder/'negative.log')
            assert 'Synthetic disabled source hash differs' in (folder/'negative.log').read_text()
            pairs[state,candidate]={'rows':samples,'triggers':proof['triggers']}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        faulty=pairs['faulted',candidate]['rows'];healthy=pairs['healthy',candidate]['rows']
        assert all(a['native_frame']==b['native_frame'] and a['time_s']==b['time_s']
            and a['throttle_command']==b['throttle_command'] and a['brake_command']==b['brake_command']
            and a['scripted_reference_visible']==b['scripted_reference_visible']
            for a,b in zip(faulty,healthy))
        for state in ('faulted','healthy'):
            t=pairs[state,candidate]['triggers']
            assert t['propulsion_test_frames']==(90 if candidate=='fallback2' else 60)
            assert t['scripted_reference_visible_fraction']==(1.0 if candidate=='fallback3' else .887324)
            assert t['fault_observation_frames']==(0 if state=='healthy' else (220 if candidate=='fallback1' else 160))
            assert t['original_camera_pixels_verified'] is False
    summary={'format':'c10052-exception-b-package-independent-audit-v1','passed':True,
        'positive_package_receipts':8,'changed_source_negatives':8,
        'controlled_fault_healthy_pairs':4,'scope':'unselected synthetic saved package processing',
        'original_native_capture_executed':False,'accepted':False}
    (HERE/'exception-b-package-audit-v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':main()
