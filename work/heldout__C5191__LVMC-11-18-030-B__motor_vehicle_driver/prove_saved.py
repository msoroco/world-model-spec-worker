"""Run every C5191 exact case through saved-only processing."""
from hashlib import sha256
import json,shutil,subprocess,sys
from pathlib import Path
from time import time_ns
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];MANIFEST=HERE/'execution-manifest.json'
def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def call(command,log):
 with log.open('w') as stream:subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
def prove(entry):
 case=entry['case_id'];short=case.rsplit('__',1)[-1];prefix=ROOT/'.runtime-work'/('c5191-saved-'+short+'-'+str(time_ns()));fixture,attempt,output=(Path(str(prefix)+suffix) for suffix in ('-fixture','-attempt','-processing'))
 call([sys.executable,'runtime.py','fixture','--recipe',str(ROOT/entry['fixture_recipe']),'--output',str(fixture)],HERE/(short+'-saved-fixture.log'))
 call([sys.executable,'runtime.py','materialize','--manifest',str(MANIFEST),'--case',case,'--output',str(attempt)],HERE/(short+'-saved-materialize.log'))
 for source in fixture.iterdir():
  target=attempt/source.name
  if target.exists():raise ValueError('Fixture shadows construction: '+source.name)
  if source.is_dir():shutil.copytree(source,target)
  else:shutil.copy2(source,target)
 command=[sys.executable,'runtime.py','process-saved','--manifest',str(MANIFEST),'--case',case,'--attempt',str(attempt),'--output',str(output),'--library','runtime/library','--validator',str(ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck')]
 log=HERE/(short+'-saved-processing.log');call(command,log);receipt=output/'v0001/processing.json';data=json.loads(receipt.read_text())
 if data.get('passed') is not True or data.get('missing_evidence') is not False or data.get('originals_preserved') is not True or data.get('analysis_revision',{}).get('construction_sha256')!=entry['construction_sha256']:raise ValueError('C5191 saved turn processing failed')
 proof={'format':'worker-saved-processing-proof','case_id':case,'construction_sha256':entry['construction_sha256'],'manifest_sha256':digest(MANIFEST),'command':' '.join(command),'exit_code':0,'log':log.name,'log_sha256':digest(log),'receipt_sha256':digest(receipt),'originals_preserved':True,'missing_evidence':False,'physical_acceptance_claimed':False}
 (HERE/(short+'-saved-proof.json')).write_text(json.dumps(proof,indent=2)+'\n');(HERE/(short+'-saved-processing-gate.log')).write_text('PASS exact C5191 saved-only original preservation, analysis, converter, renderer and four-camera decode\n')
if __name__=='__main__':
 for e in json.loads(MANIFEST.read_text())['cases']:prove(e)
