"""Run one exact saved-only diagnostic fixture through v6 processing."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v6/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
from worker_exchange.package_compatibility import materialize_case

folder=ROOT/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver'
entry=next(e for e in json.loads((folder/'execution-manifest.json').read_text())['cases'] if e['case_id'].endswith('__base'))
work=ROOT/'.runtime-work/v6-saved-integration'
if work.exists():shutil.rmtree(work)
clone=work/'package';clone.mkdir(parents=True)
shutil.copyfile(folder/'execution-manifest.json',clone/'execution-manifest.json')
(clone/'proposals').mkdir();shutil.copyfile(folder/'proposals/cases.json',clone/'proposals/cases.json')
for candidate in [entry, *entry['candidates']]:
    path=Path(candidate['construction']);target=clone/path;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(folder/path,target)
fixture=work/'fixture'
materialize(ROOT,ROOT/entry['fixture_recipe'],fixture)
attempt=work/'attempt'
materialize_case(clone/'execution-manifest.json',entry['case_id'],attempt,fixture)
argv=[str(ROOT/'.venv-cpu/bin/python'),str(ROOT/'runtime.py'),'process-saved',
      '--manifest',str(clone/'execution-manifest.json'),'--case',entry['case_id'],
      '--attempt',str(attempt),'--output',str(work/'processed'),
      '--library',str(ROOT/'runtime/main-pipeline-v6/library'),
      '--validator',str(ROOT/'.runtime-work/v6-selftest-proof/decoder/.lake/build/bin/adapterCheck')]
result=subprocess.run(argv,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(work/'process-saved.log').write_text(result.stdout)
print('exit',result.returncode)
print(result.stdout[-2000:])
if result.returncode:raise SystemExit(result.returncode)
receipt=json.loads((work/'processed/v0001/processing.json').read_text())
assert receipt['passed'] and receipt['recorded_only'] and receipt['originals_preserved']
assert receipt['candidate_id']=='primary' and receipt['analysis_revision']['runtime_manifest_sha256']==json.loads((clone/'execution-manifest.json').read_text())['runtime_manifest_sha256']
print(json.dumps({'saved_processing':True,'recorded_only':True,'originals_preserved':True,'candidate_id':receipt['candidate_id']}))
