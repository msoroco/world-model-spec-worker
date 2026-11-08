"""Independent saved package receipt and controlled-pair audit."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from measure_facility import overlap_area
from pedestrian_engineering import CONFLICT_BOUNDS_M
from worker_exchange.common import digest,tree

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def main():
    manifest=read(HERE/'draft-pedestrian-execution-manifest.json')
    pairs={}
    for response in ('clear','conflict'):
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            label=response+'-'+candidate
            proof=read(HERE/('pedestrian-package-'+label+'.json'))
            assert proof['passed'] is True and proof['accepted'] is False
            assert proof['selected'] is False and proof['original_native_capture_executed'] is False
            assert proof['manifest_sha256']==sha(HERE/'draft-pedestrian-execution-manifest.json')
            entry=next(e for e in manifest['cases'] if e['case_id']==proof['case_id'])
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            assert proof['construction_sha256']==selected['construction_sha256']==sha(HERE/selected['construction'])
            fixture=ROOT/proof['source_root'];output=ROOT/proof['output_root']
            receipt=read(output/'compatibility.json')
            assert proof['positive_receipt_sha256']==sha(output/'compatibility.json')
            assert receipt['passed'] is True and receipt['fixture_sha256']==digest(tree(fixture))
            assert receipt['construction_sha256']==proof['construction_sha256']
            assert set(receipt['checks'])>={'actual_analysis','native_validation','mandatory_observations',
                'lean_decoder','render','final_decode','acquisition_unchanged'}
            assert all(read(output/name)['passed'] for name in ('source-0.json','source-1.json',
                'source-2.json','source-3.json','final-decode.json'))
            report=read(output/'analysis-report.json');result=read(output/'result.json')
            assert report['accepted'] is False and result['accepted'] is False
            assert report['source_scope']=='synthetic_cpu_fixture'
            assert report['video_frames']=={name+'.mkv':480 for name in
                ('overview','approach','reference_corner','driver_reference')}
            rows=[json.loads(line) for line in (fixture/'pedestrian_native_samples.jsonl').read_text().splitlines()]
            assert len(rows)==480
            assert read(fixture/'pedestrian-source-manifest.json')['samples_sha256']==sha(fixture/'pedestrian_native_samples.jsonl')
            assert all(row['native_frame']==1000+i and row['time_s']==round(i/20,2)
                for i,row in enumerate(rows))
            ego={i for i,row in enumerate(rows) if overlap_area(row['ego_body_xy'],CONFLICT_BOUNDS_M)>.01}
            ped={i for i,row in enumerate(rows) if overlap_area(row['pedestrian_body_xy'],CONFLICT_BOUNDS_M)>.01}
            overlap=len(ego&ped)
            assert overlap==(0 if response=='clear' else 20)
            assert overlap==proof['simultaneous_conflict_frames']==report['measurements']['simultaneous_conflict_frames']
            assert report['measurements']['qualifying_synthetic_geometry'] is True
            negative=ROOT/proof['output_root']/'..'/'negative.log'
            assert proof['negative_exit_code']!=0 and proof['negative_log_sha256']==sha(negative)
            assert 'Synthetic pedestrian source hash differs' in negative.read_text()
            assert not (negative.parent/'negative/result.json').exists()
            pairs[response,candidate]={'overlap':overlap,'triggers':proof['triggers']}
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        assert pairs['clear',candidate]['overlap']==0
        assert pairs['conflict',candidate]['overlap']==20
        for response in ('clear','conflict'):
            trigger=pairs[response,candidate]['triggers']
            assert trigger['approach_runway_m']==(46.0 if candidate=='fallback1' else 36.0)
            assert trigger['ego_entry_error_frames']==(5 if candidate=='fallback2' else 0)
            assert trigger['synthetic_visible_fraction']==(1.0 if candidate=='fallback3' else .888889)
            assert trigger['original_camera_pixels_verified'] is False
    summary={'format':'c10052-pedestrian-package-independent-audit-v1','passed':True,
        'positive_package_receipts':8,'changed_source_negatives':8,
        'controlled_clear_conflict_pairs':4,'scope':'unselected synthetic saved package processing',
        'original_native_capture_executed':False,'accepted':False}
    (HERE/'pedestrian-package-audit-v1.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':main()
