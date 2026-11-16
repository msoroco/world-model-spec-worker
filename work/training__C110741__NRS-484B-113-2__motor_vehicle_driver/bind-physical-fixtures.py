"""Run and bind three physical outcome mocks and a lifecycle fixture per selected case."""
import hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent.parent
sys.path.insert(0,str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.physical_preparation import validate
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def main():
 manifest=HERE/'execution-manifest.json'; data=json.loads(manifest.read_text())
 for entry in data['cases']:
  suffix=entry['case_id'].split('__')[-1];folder=HERE/'physical-fixtures'/suffix;folder.mkdir(parents=True,exist_ok=True)
  fixtures=[];lifecycle=None
  for kind in ('complete_motion','incomplete_motion','missing_evidence','lifecycle'):
   out=folder/(kind+'.json');log=folder/(kind+'.log')
   command=f'.venv-cpu/bin/python work/{HERE.name}/prove-physical-fixtures.py --suffix {suffix} --kind {kind} --output work/{HERE.name}/physical-fixtures/{suffix}/{kind}.json'
   run=subprocess.run(command.split(),cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
   log.write_text(run.stdout)
   if run.returncode:raise ValueError(command+' failed: '+run.stdout)
   if kind=='lifecycle':lifecycle={'events':json.loads(out.read_text())['events'],'exit_code':0,'log':str(log.relative_to(HERE)),'log_sha256':sha(log)}
   else:fixtures.append({'kind':kind,'command':command,'exit_code':0,'log':str(log.relative_to(HERE)),'log_sha256':sha(log),'result':str(out.relative_to(HERE)),'result_sha256':sha(out)})
  proof={'format':'c110741-physical-cpu-fixtures-v1','case_id':entry['case_id'],'construction_sha256':entry['construction_sha256'],'fixtures_are_cpu_mocks':True,'original_native_motion_verified':False,'fixtures':fixtures,'lifecycle':lifecycle}
  path=folder/'proof.json';write(path,proof)
  spec={'receipt':str(path.relative_to(HERE)),'sha256':sha(path)}
  validate(ROOT,HERE,{**entry,'physical_preparation':spec});entry['physical_preparation']=spec
 write(manifest,data);print(json.dumps({'selected_cases':len(data['cases']),'cpu_outcomes':6,'lifecycle_fixtures':2,'manifest_sha256':sha(manifest)}))
if __name__=='__main__':main()
