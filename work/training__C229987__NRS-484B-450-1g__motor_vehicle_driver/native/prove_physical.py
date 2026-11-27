"""Run synthetic complete, incomplete, missing, and ownership lifecycle checks."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
repo=root.parents[1]
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    folder=root/'physical-proof'/suffix
    folder.mkdir(parents=True,exist_ok=True)
    fixtures=[]
    for kind in ('complete_motion','incomplete_motion','missing_evidence'):
        output=folder/(kind+'.json');log=folder/(kind+'.log')
        command=[sys.executable,str(root/'physical_preparation.py'),'--case',case,'--kind',kind,'--output',str(output)]
        run=subprocess.run(command,cwd=repo,text=True,capture_output=True)
        log.write_text(run.stdout+run.stderr)
        assert run.returncode==0,(kind,run.stderr)
        fixtures.append({'kind':kind,'command':' '.join(command),'exit_code':0,
                         'log':str(log.relative_to(root)),'log_sha256':sha(log),
                         'result':str(output.relative_to(root)),'result_sha256':sha(output)})
    log=folder/'lifecycle.log';output=folder/'lifecycle.json'
    command=[sys.executable,str(root/'physical_preparation.py'),'--case',case,'--kind','lifecycle','--output',str(output)]
    run=subprocess.run(command,cwd=repo,text=True,capture_output=True)
    log.write_text(run.stdout+run.stderr)
    assert run.returncode==0
    life=json.loads(output.read_text())
    life.update(case_id=case,construction_sha256=entry['construction_sha256'],
                provenance_kind='synthetic_fixture',diagnostic_fixture=True,
                original_native_observed=False,physical_acceptance_claimed=False,
                log=str(log.relative_to(root)),log_sha256=sha(log))
    proof={'format':'c229987-signal-physical-cpu-v1','case_id':case,
           'construction_sha256':entry['construction_sha256'],'fixtures':fixtures,
           'lifecycle':life,'diagnostic_only':True,'original_native_observed':False}
    path=folder/'proof.json';path.write_text(json.dumps(proof,indent=2)+'\n')
    entry['physical_preparation']={'receipt':str(path.relative_to(root)),'sha256':sha(path)}
manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
