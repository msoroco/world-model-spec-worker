"""Run each exact unselected exception bundle through pinned v1 diagnostics."""
from __future__ import annotations
import argparse
import importlib.util
import json
import hashlib
from pathlib import Path
import shutil
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

CASES=('exception_1_1','exception_1_2','exception_2_1','exception_2_2','exception_3_1','exception_3_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def prove(suffix):
    case=HERE.name+'__'+suffix
    manifest=HERE/'draft-exception-execution-manifest.json'
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c110454-lvmc-excase-'))
    source=scratch/'fixture'
    fixture.make_attempt(source,suffix,full_resolution=True)
    if suffix in ('exception_2_2','exception_3_2'):
        capture_manifest=source/'capture/manifest.json'
        meta=json.loads(capture_manifest.read_text())
        meta['sources']['road.xodr']=hashlib.sha256((HERE/'native/road_exception_device.xodr').read_bytes()).hexdigest()
        capture_manifest.write_text(json.dumps(meta))
    (source/'config.json').unlink()
    (source/'road.xodr').unlink()
    outcomes=[]
    for candidate in CANDIDATES:
        output=scratch/('output-'+candidate)
        receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
            ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',candidate)
        negative=scratch/('negative-'+candidate)
        materialize_case(manifest,case,negative,source,candidate)
        (negative/'exception_context.json').unlink()
        failed=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
            '--output',str(negative/'analysis-report.json')],cwd=negative,env=execution_env(),
            text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        expected='Missing required source: exception_context.json'
        if failed.returncode==0 or expected not in failed.stdout:
            raise RuntimeError(f'{suffix}/{candidate} negative source rejection failed: '+failed.stdout)
        folder=HERE/'draft-candidates'/suffix/candidate
        shutil.copy2(output/'compatibility.json',folder/'diagnostic-compatibility.json')
        shutil.copy2(output/'compatibility-analysis.log',folder/'analysis-compatibility.log')
        (folder/'negative-analysis.log').write_text(failed.stdout)
        (folder/'compatibility.log').write_text(json.dumps({'positive_passed':receipt['passed'],
            'checks':receipt['checks'],'negative_exit_code':failed.returncode,
            'negative_expected_error':expected,'synthetic_diagnostic':True},indent=2)+'\n')
        outcomes.append({'candidate':candidate,'construction_sha256':receipt['construction_sha256'],
            'compatibility_passed':receipt['passed'],'negative_exit_code':failed.returncode})
    return {'suffix':suffix,'scratch':str(scratch),'outcomes':outcomes}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--suffix',choices=CASES,required=True)
    args=parser.parse_args()
    print(json.dumps(prove(args.suffix),indent=2))
