"""Independently bind selected CPU receipts to exact selected constructions."""
from __future__ import annotations
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
REQUIRED={'actual_analysis','native_validation','mandatory_observations','lean_decoder',
 'render','final_decode','acquisition_unchanged','derived_outputs_rebuilt',
 'four_camera_sources','selected_measurements','negative_case_source'}

def audit():
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    summary=json.loads((HERE/'selected-matrix-summary.json').read_text())
    matrix={(r['case'],r['candidate']):r for r in summary['results']}
    checked=[]
    for entry in manifest['cases']:
        case=entry['case_id'].split('__')[-1]
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            if (case,candidate)==('witness_1','primary'):
                prefix=ROOT/'.runtime-work/c111256-selected'
                offline=ROOT/'.runtime-work/c111256-selected-offline-witness1'
                output=ROOT/'.runtime-work/c111256-selected-compat-witness1'
                saved=ROOT/'.runtime-work/c111256-selected-saved-witness1'
            else:
                row=matrix[(case,candidate)];assert row['passed']
                prefix=ROOT/'.runtime-work'/('c111256-selected-'+case+'-'+candidate)
                offline=Path(str(prefix)+'-offline');output=Path(str(prefix)+'-compat')
                saved=Path(str(prefix)+'-saved')
                assert sha(offline/'offline.log')==row['offline_log_sha256']
                assert sha(output/'compatibility.json')==row['compatibility_receipt_sha256']
                assert sha(saved/'v0001/processing.json')==row['saved_receipt_sha256']
            a=json.loads((output/'compatibility.json').read_text())
            b=json.loads((saved/'v0001/processing.json').read_text())
            selected=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            assert a['passed'] and a['case_id']==entry['case_id'] and a['candidate_id']==candidate
            assert a['construction_sha256']==selected['construction_sha256']
            assert a['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
            assert REQUIRED<=set(a['checks']) and a['negative_removed']=='road_geometry.json'
            assert a['negative_error_contains']=='Missing required source: road_geometry.json'
            assert b['passed'] and b['case_id']==entry['case_id'] and b['candidate_id']==candidate
            assert b['originals_preserved'] and not b['missing_evidence']
            assert b['timestamp_joins']=={'frames':480,'passed':True,'missing_original_trace_or_map':False}
            assert b['final_video_checks']['passed'] and not b['physical_acceptance_claimed']
            assert not b['legal_acceptance_claimed']
            assert (offline/'offline.log').is_file()
            checked.append({'case':case,'candidate':candidate,'construction_sha256':selected['construction_sha256'],
                'offline_log_sha256':sha(offline/'offline.log'),
                'compatibility_sha256':sha(output/'compatibility.json'),
                'saved_sha256':sha(saved/'v0001/processing.json')})
    assert len(checked)==16 and len(matrix)==15
    return {'format':'c111256-selected-runtime-independent-audit','passed':True,
        'selected_case_count':4,'candidate_count':16,'negative_count':16,'saved_count':16,
        'scope':'selected CPU diagnostics only; no physical or legal acceptance','checked':checked}
if __name__=='__main__':
    x=audit();(HERE/'selected-matrix-audit.json').write_text(json.dumps(x,indent=2)+'\n')
    print('audited',x['candidate_count'],'selected candidate chains')
