"""Four 480-frame saved statutory source positives and removed-context negatives."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import verify_report
spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-statutory-fixture.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
CASES=('rail_reference','rail_contrast','oneway_absent','oneway_present')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(folder):
    return {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*')
           if p.is_file() and p.name not in ('analysis-report.json','result.json')}

def main():
    env=dict(os.environ);env['PYTHONPATH']=os.pathsep.join((str(ROOT/'runtime/pipeline/scenario_pipeline'),
        str(ROOT/'runtime/pipeline/python'),str(ROOT/'runtime/pipeline'),
        str(HERE/'native'),env.get('PYTHONPATH','')))
    rows=[]
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c110454-213-statproof-') as temp:
        scratch=Path(temp)
        for suffix in CASES:
            base=scratch/(suffix+'-base');fixture.make_base(base,suffix,480)
            good=scratch/(suffix+'-positive');bad=scratch/(suffix+'-negative')
            shutil.copytree(base,good);shutil.copytree(base,bad)
            before=digest(good)
            command=[sys.executable,str(HERE/'native/finalize_statutory.py'),
                '--attempt',str(good),'--output',str(good/'analysis-report.json')]
            positive=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            if positive.returncode:raise RuntimeError(suffix+' saved positive failed: '+positive.stdout)
            if before!=digest(good):raise ValueError('Saved finalizer mutated original acquisition')
            report=json.loads((good/'analysis-report.json').read_text())
            contract=json.loads((HERE/'draft-statutory-contracts'/suffix/'measurement-contract.json').read_text())
            verify_report(contract,report,good)
            result=json.loads((good/'result.json').read_text())
            (bad/'statutory_context.json').unlink()
            failed=subprocess.run([sys.executable,str(HERE/'native/finalize_statutory.py'),
                '--attempt',str(bad),'--output',str(bad/'analysis-report.json')],
                text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env)
            expected='Missing required source: statutory_context.json'
            if failed.returncode==0 or expected not in failed.stdout:
                raise ValueError('Missing statutory source negative passed: '+failed.stdout)
            rows.append({'case_suffix':suffix,'positive_exit_code':positive.returncode,
                'negative_exit_code':failed.returncode,'negative_error':expected,
                'sampled_relation':report['measurements']['statutory_approach_relation']['value']['sampled_relation'],
                'one_way':report['measurements']['statutory_context']['value']['one_way'],
                'railroad_crossing':report['measurements']['statutory_context']['value']['railroad_crossing'],
                'source_unchanged':True,'frames':report['original_joins']['frames'],
                'video_frames':report['video_frames'],'accepted':result['accepted'],
                'analysis_sha256':sha(good/'analysis-report.json')})
    return {'format':'c110454-213-statutory-saved-proof-v1','passed':True,'results':rows,
        'scope':'synthetic 480-frame source schema and saved video decode; no Native physical or legal conclusion'}

if __name__=='__main__':print(json.dumps(main(),indent=2))
