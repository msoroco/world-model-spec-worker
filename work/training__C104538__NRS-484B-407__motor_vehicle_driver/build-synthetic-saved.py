"""Retain a tiny synthetic saved-source finalizer diagnostic, never a Native run."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT/'native'))
from test_finalize import CAMERAS,prepare


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    base=ROOT/'draft-saved-v2'/'base'
    if base.exists():raise ValueError('Retain prior synthetic diagnostic; use a new version')
    base.mkdir(parents=True)
    prepare(base)
    config=json.loads((base/'config.json').read_text())
    config['synthetic_fixture']=True
    (base/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    binary=REPO/'.runtime-work/linux_arm64/ffmpeg'
    probe=REPO/'.runtime-work/linux_arm64/ffprobe'
    if not binary.is_file() or not probe.is_file():
        raise ValueError('Local synthetic diagnostic video tools unavailable')
    for name in CAMERAS:
        path=base/(name+'.mkv');path.unlink()
        subprocess.run([str(binary),'-nostdin','-hide_banner','-loglevel','error','-n',
            '-f','lavfi','-i','color=c=black:s=16x16:r=1:d=3',
            '-frames:v','3','-c:v','ffv1',str(path)],check=True,timeout=120)
    env=dict(os.environ);env['PATH']=str(binary.parent)+os.pathsep+env.get('PATH','')
    env['PYTHONPATH']=os.pathsep.join([str(REPO/'runtime/pipeline/scenario_pipeline'),
                                     str(ROOT/'native'),env.get('PYTHONPATH','')])
    rows=[]
    for label,removed,expected in (
        ('positive',None,None),
        ('negative_missing_evidence','capture/evidence.jsonl','Missing required source'),
        ('negative_missing_video','reference_left.mkv','Missing required source')):
        attempt=ROOT/'draft-saved-v2'/label
        shutil.copytree(base,attempt)
        if removed:(attempt/removed).unlink()
        command=['python3.11',str(ROOT/'native/finalize.py'),
                 '--attempt',str(attempt),'--output',str(attempt/'analysis-report.json')]
        result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=120)
        log=ROOT/'draft-saved-v2'/(label+'.log');log.write_text(result.stdout+result.stderr)
        if expected is None:
            assert result.returncode==0,(label,result.stderr)
        else:
            assert result.returncode!=0 and expected in result.stderr,(label,result.stderr)
        rows.append({'label':label,'removed':removed,'exit_code':result.returncode,
                     'log':str(log.relative_to(ROOT)),'log_sha256':sha(log)})
    summary={'format':'c104538-synthetic-saved-diagnostic-v2',
        'positive_count':1,'negative_count':2,'rows':rows,
        'positive_result_sha256':sha(ROOT/'draft-saved-v2/positive/result.json'),
        'positive_analysis_sha256':sha(ROOT/'draft-saved-v2/positive/analysis-report.json'),
        'native_executed':False,'recording_accepted':False,
        'scope':'three-frame synthetic saved finalizer diagnostic; not exact 480-frame package compatibility'}
    (ROOT/'draft-saved-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':print(json.dumps(build()))
