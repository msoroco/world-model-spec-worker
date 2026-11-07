"""Exercise pinned exact package compatibility for an unselected 3(a) draft."""
import importlib.util
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
spec2=importlib.util.spec_from_file_location('graphs',HERE/'probe-core-synthetic.py')
graphs=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(graphs)
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env
from worker_exchange.media import compose_four_views


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=['controlled_1','controlled_2'],default='controlled_1')
    parser.add_argument('--candidate',choices=['primary','fallback1','fallback2','fallback3'],default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c394300-3a-exact-'))
    source=scratch/'fixture';fixture.build(source,args.case,full_resolution=True)
    graphs.add_synthetic_graphs(source)
    compose_four_views({name:source/(name+'.mkv') for name in
        ('overview','approach','reference_corner','driver_reference')},
        source/'video_frames.jsonl',source/'raw.mkv')
    (source/'config.json').unlink()
    case=HERE.name+'__'+args.case
    output=scratch/'output'
    print('scratch',scratch,flush=True)
    receipt=run(HERE/'draft-execution-manifest.json',case,source,output,
        ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(HERE/'draft-execution-manifest.json',case,negative,source,args.candidate)
    (negative/'declared_purpose.json').unlink()
    failure=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
        '--output',str(negative/'analysis-report.json')],cwd=negative,env=execution_env(),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    expected='Missing required source: declared_purpose.json'
    if failure.returncode==0 or expected not in failure.stdout:
        raise RuntimeError('Exact missing-purpose negative did not reject: '+failure.stdout)
    print(json.dumps({'positive':{k:v for k,v in receipt.items() if k!='fixture_manifest'},
        'negative':{'exit_code':failure.returncode,'removed':'declared_purpose.json',
            'error_contains':expected},'case':args.case,'candidate':args.candidate,
        'scope':'unselected diagnostic exact package, not selected strict v2 delivery'}))


if __name__=='__main__':main()
