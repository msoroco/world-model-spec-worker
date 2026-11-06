"""Exact synthetic v1 package integration plus missing-source negative."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('c104538_core_fixture',FOLDER/'probe-core-synthetic.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('witness_1','witness_2'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c104538-package-'))
    seeded=fixture.make_attempt(scratch/'seeded',args.case,args.candidate)
    source=scratch/'source';source.mkdir()
    files=('native_samples.jsonl','video_frames.jsonl','body_history.jsonl','trace.jsonl',
           'context.json','road.xodr','sign-review.json','overview.mkv','approach.mkv',
           'sign_reference.mkv','driver_reference.mkv')
    for name in files:shutil.copyfile(seeded/name,source/name)
    for name in ('capture','channels','source_channels'):
        shutil.copytree(seeded/name,source/name)
    case=FOLDER.name+'__'+args.case
    output=scratch/'positive'
    receipt=run(FOLDER/'draft-execution-manifest.json',case,source,output,
        ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(FOLDER/'draft-execution-manifest.json',case,negative,source,args.candidate)
    (negative/'native_samples.jsonl').unlink()
    failure=subprocess.run([sys.executable,str(negative/'finalize.py'),
        '--attempt',str(negative),'--output',str(negative/'analysis-report.json')],
        cwd=negative,env=execution_env(),text=True,stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(failure.stdout)
    if failure.returncode==0 or 'Missing required source: native_samples.jsonl' not in failure.stdout:
        raise RuntimeError('Exact package missing-source negative failed: '+failure.stdout)
    print(json.dumps({'scratch':str(scratch),'case':args.case,'candidate':args.candidate,
        'positive':{k:v for k,v in receipt.items() if k!='fixture_manifest'},
        'negative':{'removed':'native_samples.jsonl','rejected':True},
        'scope':'synthetic v1 diagnostic only; strict v2 still pending'},indent=2))


if __name__=='__main__':main()
