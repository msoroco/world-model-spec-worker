"""Rebind all exact construction plans after a root case-plan revision."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
PLAN=(HERE/'case-plan.json').read_text()

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def bind_manifest(name):
    path=HERE/name
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        for choice in [entry,*entry.get('candidates',[])]:
            construction=HERE/choice['construction']
            value=json.loads(construction.read_text())
            value['files']=[item for item in value['files']
                            if not item['path'].startswith('tests/')
                            and item['path']!='overtake_comparison_audit.py']
            runner_test = ('test_delivery_runner.py' if entry['case_id'].endswith('__left_pass_wide')
                           else 'test_overtake_variants.py')
            for name in (runner_test,'test_overtake_camera.py',
                         'test_overtake_finalizer.py','test_overtake_measurement.py',
                         'test_overtake_route.py','test_overtake_source_capture.py'):
                test_path='tests/'+name
                value['files'].append({'path':test_path,'content':(HERE/test_path).read_text()})
            row=next(item for item in value['files'] if item['path']=='case-plan.json')
            row['content']=PLAN
            construction.write_text(json.dumps(value,indent=2)+'\n')
            choice['construction_sha256']=digest(construction)
            if 'offline' in choice:
                choice['offline']['construction_sha256']=choice['construction_sha256']
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    first=bind_manifest('delivery-construction-manifest.json')
    variants=bind_manifest('variant-construction-manifest.json')
    execution=json.loads((HERE/'execution-manifest.json').read_text())
    by_id={e['case_id']:e for e in first['cases']+variants['cases']}
    for entry in execution['cases']:
        source=by_id[entry['case_id']]
        entry['construction_sha256']=source['construction_sha256']
        entry['offline']['construction_sha256']=source['construction_sha256']
        for candidate,changed in zip(entry['candidates'],source['candidates']):
            candidate['construction_sha256']=changed['construction_sha256']
            candidate['offline']['construction_sha256']=changed['construction_sha256']
    (HERE/'execution-manifest.json').write_text(json.dumps(execution,indent=2)+'\n')
    print('Rebound four primaries and twelve fallbacks to current case plan')
