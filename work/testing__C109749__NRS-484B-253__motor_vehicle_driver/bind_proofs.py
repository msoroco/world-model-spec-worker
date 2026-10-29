"""Bind one partition-one case's passed exact offline and compatibility receipts."""
import argparse,hashlib,json,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('assignment_id');p.add_argument('offline_dir');p.add_argument('compat_dir');p.add_argument('handoff_note');a=p.parse_args()
root=Path('work')/a.assignment_id;off=Path(a.offline_dir);compat=Path(a.compat_dir)
for source,target in [(off/'offline.log',root/'receipts/offline.log'),(compat/'compatibility.json',root/'receipts/compatibility.json'),(compat/'compatibility-analysis.log',root/'receipts/analysis.log'),(compat/'negative-analysis.log',root/'receipts/negative.log')]:
    shutil.copyfile(source,target)
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
manifest_path=root/'execution-manifest.json';manifest=json.loads(manifest_path.read_text());entry=manifest['cases'][0];case=entry['case_id']
offline_command='flock .runtime-work/runtime.lock .venv-cpu/bin/python runtime.py offline --manifest work/'+root.name+'/execution-manifest.json --case '+case+' --output '+a.offline_dir+' --python /global/homes/m/msoroco/scratch/scenario-worker-demo-test-trial6/.venv-cpu/bin/python'
compat_command='flock .runtime-work/runtime.lock .venv-cpu/bin/python runtime.py compatibility-recipe --manifest work/'+root.name+'/execution-manifest.json --case '+case+' --output '+a.compat_dir+' --library .runtime-work/overlay/library --validator .runtime-work/decoder-build/.lake/build/bin/adapterCheck'
entry['offline']={'command':offline_command,'exit_code':0,'log':'receipts/offline.log','log_sha256':sha(root/'receipts/offline.log'),'construction_sha256':entry['construction_sha256']}
entry['compatibility']={'command':compat_command,'receipt':'receipts/compatibility.json','sha256':sha(root/'receipts/compatibility.json'),'log':'receipts/analysis.log'}
entry['negative']={'log':'receipts/negative.log','sha256':sha(root/'receipts/negative.log')}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
batch=json.loads(Path('batch.json').read_text())
gpu='python3.11 runtime.py capture --manifest work/'+root.name+'/execution-manifest.json --case '+case+' --output .runtime-work/attempts/'+case+' --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT"'
result={'assignment_id':root.name,'input_sha256':batch['assignments'][root.name]['input_sha256'],'applied_update':batch['update_version'],'status':'ready','readiness_kind':'capability','first_gpu_capability_command':gpu,'tests':[{'command':offline_command,'exit_code':0,'log':'receipts/offline.log','sha256':sha(root/'receipts/offline.log')},{'command':compat_command,'exit_code':0,'log':'receipts/analysis.log','sha256':sha(root/'receipts/analysis.log')}],'limitations':['No CARLA run or physical acceptance.',a.handoff_note]}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
(root/'HANDOFF.md').write_text('# Exact capability handoff\n\n'+a.handoff_note+' The retained diagnostic recipe proves software compatibility only. Physical motion, pixels and legal conclusions remain local review. No CARLA or physical acceptance is claimed.\n\nFirst GPU capability command: `'+gpu+'`\n')
print(json.dumps({'case_id':case,'offline_log_sha256':entry['offline']['log_sha256'],'compatibility_receipt_sha256':entry['compatibility']['sha256'],'negative_log_sha256':entry['negative']['sha256']}))
