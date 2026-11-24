"""Bind both exact speed cases to retained construction sources for selected CPU reproof."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def main():
    cases=[]
    for label,index in (('below',1),('above',2)):
        case=HERE.name+f'__controlled_{index}'
        source=json.loads((HERE/f'current-v2-{label}-construction.json').read_text())
        source['status']='partial_selected_cpu_diagnostic_physical_unverified'
        for entry in source['files']:
            if entry['path']=='config.json':
                config=json.loads(entry['content']);config['status']='partial_selected_cpu_diagnostic_physical_unverified'
                entry['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
        path=HERE/f'selected-candidates/{label}/primary/construction.json';write(path,source)
        cases.append({'case_id':case,'kind':'delivery','id':'primary',
          'construction':str(path.relative_to(HERE)),'construction_sha256':sha(path),
          'fixture_recipe':str((HERE/f'current-v2-{label}-fixture-recipe.json').relative_to(REPO)),
          'measurement_contract':f'current-v2-{label}-measurement-contract.json',
          'measurement_procedure':{'entrypoint':'finalize.py'},
          'recording_description':source['recording_description'],
          'candidate_risk':{'status':'physical','reason':'Native arc/exit traversal and target speed attainment unverified'},
          'candidates':[],'preparation_status':'selected_cpu_diagnostic_reproof_pending'})
    batch=json.loads((REPO/'batch.json').read_text())
    manifest=HERE/'execution-manifest.json'
    write(manifest,{'format':'worker-execution-manifest','assignment_id':HERE.name,
      'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
      'status':'partial_selected_cpu_proofs_under_construction','cases':cases})
    print(sha(manifest))
if __name__=='__main__':main()
