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
    if summary['format']!='c111256-unselected-v1-package-diagnostics' or len(summary['results'])!=16:
        raise ValueError('Sixteen exact package diagnostics missing')
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
        receipt=json.loads(text[start:])
        positive=receipt['positive'];negative=receipt['negative']
        if receipt['case']!=entry['case_id'] or receipt['candidate']!=candidate:
            raise ValueError('Package selected another case/candidate')
        if positive['format']!='worker-package-compatibility-v1' or positive['passed'] is not True:
            raise ValueError('Positive package did not pass pinned v1 path')
        if positive['construction_sha256']!=selected['construction_sha256'] or \
           positive['runtime_manifest_sha256']!=manifest['runtime_manifest_sha256']:
            raise ValueError('Positive package source differs')
        if not REQUIRED<=set(positive['checks']):raise ValueError('Positive software stages missing')
        if negative!={'exit_code':1,'removed':'road_geometry.json',
                      'error_contains':'Missing required source: road_geometry.json'}:
            raise ValueError('Negative source removal was not rejected exactly')
        if 'synthetic diagnostic' not in receipt['scope'] or 'not selected' not in receipt['scope']:
            raise ValueError('Diagnostic scope overstated')
        checked.append({'case':case,'candidate':candidate,
                        'construction_sha256':selected['construction_sha256'],
                        'positive_checks':sorted(REQUIRED),
                        'negative_removed':'road_geometry.json'})
    if {(x['case'],x['candidate']) for x in checked}!={(case,candidate)
       for case in ('witness_1','witness_2','exception_1_1','exception_1_2') for candidate in ('primary','fallback1','fallback2','fallback3')}:
        raise ValueError('Package matrix incomplete')
    return {'passed':True,'assignment_id':HERE.name,'package_count':16,
            'scope':'unselected synthetic pinned v1 software diagnostics only',
            'physical_observations':False,'accepted_recordings':False,'checked':checked}

if __name__=='__main__':print(json.dumps(audit(),indent=2))
