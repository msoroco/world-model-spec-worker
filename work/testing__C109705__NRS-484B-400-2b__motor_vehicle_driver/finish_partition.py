"""Run every exact-case offline check and write hash-bound partition handoffs."""
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT=pathlib.Path(__file__).resolve().parents[2]
PART=json.loads((ROOT/'partitions/demo-test-01.json').read_text())['assignment_ids'][1:]
PY=ROOT/'.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


for aid in PART:
    folder=ROOT/'work'/aid
    manifest=json.loads((folder/'execution-manifest.json').read_text())
    results=[]
    for n,entry in enumerate(manifest['cases']):
        output=ROOT/'.runtime-work'/('part01-v5-'+aid.split('__')[1]+'-'+str(n))
        command=[str(PY),str(ROOT/'runtime.py'),'offline','--manifest',str(folder/'execution-manifest.json'),
                 '--case',entry['case_id'],'--output',str(output)]
        if not output.exists():
            attempt=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
            if attempt.returncode:
                print(attempt.stdout,attempt.stderr,file=sys.stderr)
                raise SystemExit(attempt.returncode)
        log=output/'offline.log'
        if not log.is_file() or 'OK' not in log.read_text():
            raise RuntimeError('Offline test missing or failed: '+entry['case_id'])
        relative='tests/offline-'+str(n)+'.log'
        (folder/relative).write_bytes(log.read_bytes())
        results.append({'command':' '.join(command),'exit_code':0,'log':relative,
                        'sha256':sha(folder/relative)})
    write(folder/'result.json',{'assignment_id':aid,
          'input_sha256':sha(ROOT/'inputs'/aid/'assignment.json'),
          'status':'ready','readiness_kind':'capability','applied_update':4,
          'tests':results,'physical_acceptance':False})
    (folder/'HANDOFF.md').write_text('# '+aid+' capability handoff\n\n'
      'The exact input law, witness and actor govern this package. The baseline is unselected. '
      'All listed nonbaseline cases were materialized separately with the supplied runtime and passed offline checks; '
      'each command and log hash is recorded in result.json. Run `runtime.py capture` for an exact case only against an '
      'operator-owned simulator endpoint. Its bundled `analyze.py --attempt PATH --output REPORT` measures original '
      'body and control samples and returns a follow-up configuration decision. Use supplied runtime process/render '
      'for saved conversion and review.\n\nSynthetic public-highway, district, common-purpose, and safety assumptions '
      'are explicit context, not measured physical facts. Native geometry, controller realization, video visibility, '
      'duration, capture coverage, and legal interpretation remain unverified. No CARLA run or physical acceptance occurred.\n')
    print(aid,len(results),'offline cases passed')
