"""Exact unselected v1 package diagnostic; never a strict v2 receipt."""
import argparse
import importlib.util
import json
import os
import pickle
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
spec = importlib.util.spec_from_file_location('c102304_fixture',HERE/'prove-saved-following.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env
from traffic_spec_adapter.adapter import load_graph


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix',choices=('condition_a','condition_b'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),required=True)
    parser.add_argument('--fixture',help='Retained immutable synthetic source fixture for this suffix')
    args = parser.parse_args()
    os.environ['PATH'] = str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    scratch = Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c102304-exact-package-'))
    if args.fixture:
        source = Path(args.fixture).resolve()
        if not source.is_relative_to(ROOT/'.runtime-work') or not source.is_dir() or (source/'config.json').exists():
            raise ValueError('Reuse only a retained unconfigured .runtime-work source fixture')
        samples = (source/'native_samples.jsonl').read_text().splitlines()
        expected_gap = 10 if args.suffix == 'condition_a' else 25
        first = json.loads(samples[0])
        gap = min(v[0] for v in first['lead']['native_body_xy_m'])-max(
            v[0] for v in first['ego']['native_body_xy_m'])
        if len(samples) != 900 or abs(gap-expected_gap)>1e-6:
            raise ValueError('Retained fixture differs from exact comparison condition')
    else:
        source = scratch/'fixture'
        fixture.make_base(source,args.suffix,os.environ,full_resolution=True)
        graph = load_graph(ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl')
        graphs = source/'capture/native/graphs/base'
        graphs.mkdir(parents=True)
        for frame in range(100,1000):
            graph.graph['frame'] = frame
            (graphs/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
        (source/'config.json').unlink()
    case = HERE.name+'__selected_ccee258c__'+args.suffix
    print('scratch',scratch,flush=True)
    output = scratch/'output'
    receipt = run(HERE/'draft-execution-manifest.json',case,source,output,
                  ROOT/'runtime/pipeline/library',
                  ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                  args.candidate)
    negative = scratch/'negative'
    materialize_case(HERE/'draft-execution-manifest.json',case,negative,source,args.candidate)
    (negative/'native_samples.jsonl').unlink()
    failure = subprocess.run([sys.executable,str(negative/'finalize.py'),
                              '--attempt',str(negative),
                              '--output',str(negative/'analysis-report.json')],
                             cwd=negative,env=execution_env(),text=True,
                             stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(failure.stdout)
    expected = 'Missing required source: native_samples.jsonl'
    if failure.returncode == 0 or expected not in failure.stdout:
        raise RuntimeError('Packaged missing-source negative accepted: '+failure.stdout)
    print(json.dumps({'case_id':case,'candidate_id':args.candidate,
                      'positive':{key:value for key,value in receipt.items() if key!='fixture_manifest'},
                      'negative':{'exit_code':failure.returncode,'removed':'native_samples.jsonl',
                                  'error_contains':expected},
                      'scope':'unselected exact v1 package diagnostic; strict v2 not proved'},
                     sort_keys=True))


if __name__ == '__main__':
    main()
