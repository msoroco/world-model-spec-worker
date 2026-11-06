"""Pinned exact v1 package positive and missing-source negative, synthetic only."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec=importlib.util.spec_from_file_location('core_fixture',HERE/'probe-core-synthetic.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suffix',choices=['witness_1','witness_2','numeric_1_0','numeric_1_1','numeric_1_2','exception_1_1','exception_1_2','exception_2_1','exception_2_2','exception_3_1','exception_3_2'],default='witness_1')
    parser.add_argument('--candidate',choices=['primary','fallback1','fallback2','fallback3'],default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c110454-lvmc-exact-'))
    source=scratch/'fixture';fixture.make_attempt(source,args.suffix,full_resolution=True)
    (source/'config.json').unlink()
    (source/'road.xodr').unlink()  # Exact construction already supplies this authored source.
    output=scratch/'output'
    print('scratch',scratch,flush=True)
    manifest=HERE/('draft-exception-execution-manifest.json' if args.suffix.startswith('exception_') else
                   'draft-numeric-execution-manifest.json' if args.suffix.startswith('numeric_')
                   else 'draft-execution-manifest.json')
    case='training__C110454__LVMC-11-52-130-A11__motor_vehicle_driver__'+args.suffix
    receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    missing='exception_context.json' if args.suffix.startswith('exception_') else 'native_parking_history.json'
    (negative/missing).unlink()
    failed=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
        '--output',str(negative/'analysis-report.json')],cwd=negative,env=execution_env(),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(failed.stdout)
    expected='Missing required source: '+missing
    if failed.returncode==0 or expected not in failed.stdout:
        raise RuntimeError('Negative exact package failed to reject Native-source removal: '+failed.stdout)
    print(json.dumps({'case_suffix':args.suffix,'candidate':args.candidate,
                      'positive':{k:v for k,v in receipt.items() if k!='fixture_manifest'},
                      'negative':{'exit_code':failed.returncode,'removed':missing,
                                  'error_contains':expected},
                      'scope':'synthetic diagnostic v1; not selected or physical'}))


if __name__=='__main__':main()
