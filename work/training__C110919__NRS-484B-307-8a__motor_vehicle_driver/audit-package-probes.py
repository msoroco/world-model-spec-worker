"""Independent audit of exact unselected v1 package positive/negative logs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REQUIRED={'actual_analysis','native_validation','mandatory_observations',
          'lean_decoder','render','final_decode','acquisition_unchanged'}

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def audit():
    summary=json.loads((HERE/'package-probes-summary.json').read_text())
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    archive=json.loads((HERE/'native/package-provenance-index.json').read_text())
    if summary['format']!='c110919-unselected-v1-package-diagnostics' or len(summary['results'])!=8:
        raise ValueError('Eight exact package diagnostics missing')
    if archive['format']!='c110919-synthetic-package-provenance-v1' or archive['assignment_id']!=HERE.name or len(archive['results'])!=8:
        raise ValueError('Retained package provenance index differs')
    checked=[]
    for item in summary['results']:
        case=item['case'];candidate=item['candidate']
        if item['exit_code']!=0:raise ValueError('Package probe failed: '+case+' '+candidate)
        entry=next(e for e in manifest['cases'] if e['case_id']==HERE.name+'__'+case)
        selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
        path=HERE/item['log']
        if sha(path)!=item['log_sha256']:raise ValueError('Package log changed')
        text=path.read_text();start=text.find('{')
        if start<0:raise ValueError('Package log has no JSON receipt')
        archived=next((x for x in archive['results'] if x['case']==case and x['candidate']==candidate),None)
        if archived is None or archived['package_log_sha256']!=sha(path):
            raise ValueError('Retained package row or log hash differs')
        paths={}
        for key,file in archived['files'].items():
            candidate_path=(HERE/file['path']).resolve()
            if HERE not in candidate_path.parents or not candidate_path.is_file() or sha(candidate_path)!=file['sha256']:
                raise ValueError('Retained package file changed: '+key)
            paths[key]=candidate_path
        if set(paths)!={'geometry','capture_manifest','result','analysis','finalizer'}:
            raise ValueError('Retained package file set differs')
        result_path=paths['result'];analysis_path=paths['analysis']
        geometry_path=paths['geometry'];capture_path=paths['capture_manifest']
        result=json.loads(result_path.read_text())
        analysis=json.loads(analysis_path.read_text())
        geometry=json.loads(geometry_path.read_text())
        capture=json.loads(capture_path.read_text())
        if not geometry.get('synthetic_diagnostic') or not capture.get('synthetic_diagnostic'):
            raise ValueError('Package fixture source labels differ')
        if result.get('provenance_kind')!='synthetic_fixture' or result.get('diagnostic_fixture') is not True or result.get('accepted') is not False:
            raise ValueError('Package result overstates provenance or acceptance')
        if analysis.get('provenance_kind')!='synthetic_fixture' or 'synthetic CPU' not in analysis.get('scope',''):
            raise ValueError('Package analysis overstates source provenance')
        receipt=json.loads(text[start:])
        positive=receipt['positive'];negative=receipt['negative']
        if receipt['case']!=entry['case_id'] or receipt['candidate']!=candidate:
            raise ValueError('Package selected another case/candidate')
        if positive['format']!='worker-package-compatibility-v1' or positive['passed'] is not True:
            raise ValueError('Positive package did not pass pinned v1 path')
        if positive['construction_sha256']!=selected['construction_sha256'] or \
           positive['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']:
            raise ValueError('Positive package source differs')
        if sha(paths['finalizer'])!=positive['analysis_sha256']:
            raise ValueError('Positive package finalizer hash differs')
        if not REQUIRED<=set(positive['checks']):raise ValueError('Positive software stages missing')
        if negative!={'exit_code':1,'removed':'road_geometry.json',
                      'error_contains':'Missing required source: road_geometry.json'}:
            raise ValueError('Negative source removal was not rejected exactly')
        if 'synthetic diagnostic' not in receipt['scope'] or 'not selected' not in receipt['scope']:
            raise ValueError('Diagnostic scope overstated')
        checked.append({'case':case,'candidate':candidate,
                        'construction_sha256':selected['construction_sha256'],
                        'result_sha256':sha(result_path),
                        'result_provenance':result['provenance_kind'],
                        'positive_checks':sorted(REQUIRED),
                        'negative_removed':'road_geometry.json'})
    if {(x['case'],x['candidate']) for x in checked}!={(case,candidate)
       for case in ('reference','contrast') for candidate in ('primary','fallback1','fallback2','fallback3')}:
        raise ValueError('Package matrix incomplete')
    return {'passed':True,'assignment_id':HERE.name,'package_count':8,
            'scope':'unselected synthetic pinned v1 software diagnostics only',
            'physical_observations':False,'accepted_recordings':False,'checked':checked}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
