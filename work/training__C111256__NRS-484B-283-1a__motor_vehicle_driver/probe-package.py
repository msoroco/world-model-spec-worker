"""Pinned synthetic v1 package path, then an exact missing-source negative."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env

spec=importlib.util.spec_from_file_location('fixture',HERE/'saved-fixture-proof.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',choices=('witness_1','witness_2'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),required=True)
    args=parser.parse_args()
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    os.environ['LD_LIBRARY_PATH']=str(ROOT/'.runtime-work/geos-wheel/shapely.libs')+os.pathsep+os.environ.get('LD_LIBRARY_PATH','')
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c111256-package-'))
    source=scratch/'fixture';fixture.make_attempt(source,args.case,full_resolution=True)
    (source/'config.json').unlink()
    print('scratch',scratch,flush=True)
    case=HERE.name+'__'+args.case
    manifest=HERE/'draft-execution-manifest.json'
    receipt=run(manifest,case,source,scratch/'output',ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    (negative/'road_geometry.json').unlink()
    result=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
        '--output',str(negative/'analysis-report.json')],cwd=negative,env=execution_env(),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(result.stdout)
    expected='Missing required source: road_geometry.json'
    if result.returncode==0 or expected not in result.stdout:
        raise RuntimeError('Negative exact package failed to reject missing road geometry: '+result.stdout)
    print(json.dumps({'case':case,'candidate':args.candidate,
      'positive':{key:value for key,value in receipt.items() if key!='fixture_manifest'},
      'negative':{'exit_code':result.returncode,'removed':'road_geometry.json',
                  'error_contains':expected},
      'scope':'synthetic diagnostic v1; not selected, physical or accepted'},indent=2))

if __name__=='__main__':main()
