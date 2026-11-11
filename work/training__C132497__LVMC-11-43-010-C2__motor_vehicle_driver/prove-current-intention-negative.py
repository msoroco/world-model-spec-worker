"""Reject absent and altered predeclared intention in the current finalizer."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE = REPO/'.runtime-work/c132497-current-all-proof/reference/primary/compatibility'
BASE = REPO/'.runtime-work/c132497-current-intention-negatives'
NEEDED = ('construction.json','config.json','native-raw-actors.jsonl',
          'trace.jsonl','video_frames.jsonl','right-exit-road.xodr',
          'controller-intention.json','finalize_current.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(kind):
    target = BASE/kind
    if target.exists():shutil.rmtree(target)
    target.mkdir(parents=True)
    for name in NEEDED:shutil.copyfile(SOURCE/name,target/name)
    if kind=='missing':
        (target/'controller-intention.json').unlink()
        expected='Missing required source: controller-intention.json'
    else:
        intention = json.loads((target/'controller-intention.json').read_text())
        intention['turn_direction']='left'
        (target/'controller-intention.json').write_text(json.dumps(intention,indent=2)+'\n')
        config = json.loads((target/'config.json').read_text())
        config['controller_intention_sha256']=sha(target/'controller-intention.json')
        (target/'config.json').write_text(json.dumps(config,indent=2)+'\n')
        expected='Predeclared right-exit controller intention differs'
    result = subprocess.run([str(REPO/'.venv-cpu/bin/python'),
             str(target/'finalize_current.py'),'--attempt',str(target),
             '--output',str(target/'analysis-report.json')],cwd=target,
             capture_output=True,text=True)
    log = ROOT/f'update015-current-intention-{kind}.log'
    log.write_text(result.stdout+result.stderr)
    if (result.returncode==0 or expected not in log.read_text() or
            (target/'result.json').exists()):
        raise ValueError('Intention negative did not reject: '+kind)
    return {'kind':kind,'expected_error':expected,'log_sha256':sha(log)}


if __name__=='__main__':
    results = [check(kind) for kind in ('missing','altered')]
    output = ROOT/'update015-current-intention-negative.json'
    output.write_text(json.dumps({'format':'c132497-current-intention-negative-v1',
                                  'passed':True,'results':results},indent=2)+'\n')
    print(json.dumps({'passed':True,'negative_rejections':len(results),
                      'proof_sha256':sha(output)}))
