"""Independently bind all public diagnostic receipts to exact case/candidate sources."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
REQUIRED={'actual_analysis','native_validation','mandatory_observations','lean_decoder','render',
          'final_decode','acquisition_unchanged','derived_outputs_rebuilt','four_camera_sources',
          'selected_measurements','negative_case_source'}

def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    summary=json.loads((HERE/'public-matrix-summary.json').read_text())
    matrix={(r['case'],r['candidate']):r for r in summary['results']}
    prior={r['case_suffix']:r for r in json.loads((HERE/'public-runtime-proof.json').read_text())['cases']}
    checked=[]
    for entry in manifest['cases']:
        suffix=entry['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            if candidate=='primary' and suffix in prior:
                stem='witness1-v3' if suffix=='witness_1' else 'exception12'
                output=ROOT/'.runtime-work'/('c111256-public-'+stem)
                saved=ROOT/'.runtime-work'/('c111256-saved-'+('witness1' if suffix=='witness_1' else 'exception12'))
                expected=prior[suffix]
                assert sha(output/'compatibility.json')==expected['compatibility_receipt_sha256']
                assert sha(saved/'v0001/processing.json')==expected['saved_processing_receipt_sha256']
            else:
                row=matrix[(suffix,candidate)]
                assert row['passed']
                key=f'{suffix}-{candidate}'
                output=ROOT/'.runtime-work'/('c111256-matrix-'+key)
                saved=ROOT/'.runtime-work'/('c111256-matrix-saved-'+key)
                assert sha(output/'compatibility.json')==row['compatibility_receipt_sha256']
                assert sha(saved/'v0001/processing.json')==row['saved_receipt_sha256']
            compatibility=json.loads((output/'compatibility.json').read_text())
            processing=json.loads((saved/'v0001/processing.json').read_text())
            selected=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            assert compatibility['passed'] and compatibility['case_id']==entry['case_id']
            assert compatibility['candidate_id']==candidate
            assert compatibility['construction_sha256']==selected['construction_sha256']
            assert compatibility['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
            assert REQUIRED<=set(compatibility['checks'])
            assert compatibility['negative_removed']=='road_geometry.json'
            assert compatibility['negative_error_contains']=='Missing required source: road_geometry.json'
            assert processing['passed'] and processing['case_id']==entry['case_id']
            assert processing['candidate_id']==candidate and processing['recorded_only']
            assert processing['originals_preserved'] and not processing['missing_evidence']
            assert processing['timestamp_joins']=={'frames':480,'passed':True,'missing_original_trace_or_map':False}
            assert processing['final_video_checks']['passed']
            assert not processing['physical_acceptance_claimed'] and not processing['legal_acceptance_claimed']
            checked.append({'case':suffix,'candidate':candidate,'construction_sha256':selected['construction_sha256'],
                            'compatibility_sha256':sha(output/'compatibility.json'),
                            'saved_sha256':sha(saved/'v0001/processing.json')})
    assert len(checked)==16 and len(matrix)==14
    return {'format':'c111256-public-runtime-independent-audit','passed':True,'candidate_count':16,
            'case_count':4,'compatibility_negative_count':16,'saved_processing_count':16,
            'scope':'synthetic CPU diagnostics only; unselected and unaccepted','checked':checked}

if __name__=='__main__':
    result=audit();(HERE/'public-matrix-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('audited',result['candidate_count'],'public compatibility and saved pairs')
