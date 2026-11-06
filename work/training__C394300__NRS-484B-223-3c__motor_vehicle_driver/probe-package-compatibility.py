"""Exercise pinned exact package compatibility on one unselected synthetic draft."""
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


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suffix',choices=['below_50_ft','at_50_ft','above_50_ft'],default='below_50_ft')
    parser.add_argument('--candidate',choices=['primary','fallback1','fallback2','fallback3'],default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c394300-3c-exact-'))
    source=scratch/'fixture';fixture.make_base(source,args.suffix,full_resolution=True)
    graphs.add_synthetic_graphs(source)
    (source/'config.json').unlink()
    output=scratch/'output'
    print('scratch',scratch,flush=True)
    case='training__C394300__NRS-484B-223-3c__motor_vehicle_driver__'+args.suffix
    receipt=run(HERE/'draft-execution-manifest.json',case,source,output,
        ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(HERE/'draft-execution-manifest.json',case,negative,source,args.candidate)
    (negative/'native_samples.jsonl').unlink()
    failed=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
                           '--output',str(negative/'analysis-report.json')],cwd=negative,
                          env=execution_env(),text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(failed.stdout)
    expected='Missing required source: native_samples.jsonl'
    if failed.returncode==0 or expected not in failed.stdout:
        raise RuntimeError('Exact negative finalization failed to reject missing source: '+failed.stdout)
    print(json.dumps({'positive':{k:v for k,v in receipt.items() if k!='fixture_manifest'},
                      'negative':{'exit_code':failed.returncode,'removed':'native_samples.jsonl',
                                  'error_contains':expected,'scope':'exact packaged finalizer'},
                      'case_suffix':args.suffix,'candidate':args.candidate}))


if __name__=='__main__':main()
