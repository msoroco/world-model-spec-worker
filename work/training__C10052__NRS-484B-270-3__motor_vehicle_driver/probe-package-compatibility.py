"""Pinned exact v1 package positive and missing-source negative, synthetic only."""
import argparse
import hashlib
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
    parser.add_argument('--suffix',choices=['probe_a','probe_b'],default='probe_a')
    parser.add_argument('--candidate',choices=['primary','fallback1','fallback2','fallback3'],default='primary')
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c10052-270-3-exact-'))
    source=scratch/'fixture';fixture.make_attempt(source,args.suffix,full_resolution=True)
    poses=fixture.rows(source/'native_samples.jsonl')
    traces=fixture.rows(source/'trace.jsonl')
    controls=[]
    for i,(pose,trace) in enumerate(zip(poses,traces)):
        held=args.suffix=='probe_b' and 160<=i<440
        control={'native_frame':pose['native_frame'],'time_s':pose['time_s'],
                 'throttle':0.0,'brake':0.5 if 132<=i<479 else 0.0,
                 'hand_brake':held,'control_source':'synthetic_fixture',
                 'synthetic_diagnostic':True}
        controls.append(control)
        trace['control']={'throttle':control['throttle'],'brake':control['brake'],
                          'hand_brake':control['hand_brake']}
    fixture.write_rows(source/'native_controls.jsonl',controls)
    fixture.write_rows(source/'trace.jsonl',traces)
    capture_manifest=json.loads((source/'capture/manifest.json').read_text())
    capture_manifest['sources']['trace.jsonl']=hashlib.sha256((source/'trace.jsonl').read_bytes()).hexdigest()
    (source/'capture/manifest.json').write_text(json.dumps(capture_manifest)+'\n')
    names=('native_samples.jsonl','native_controls.jsonl','road_geometry.json')
    (source/'park-act-sources.json').write_text(json.dumps({
        'format':'c10052-park-act-sources-v1','source_kind':'synthetic_cpu_fixture',
        'sha256':{name:hashlib.sha256((source/name).read_bytes()).hexdigest()
                  for name in names}},sort_keys=True)+'\n')
    (source/'config.json').unlink()
    output=scratch/'output'
    print('scratch',scratch,flush=True)
    manifest=HERE/'draft-execution-manifest.json'
    case='training__C10052__NRS-484B-270-3__motor_vehicle_driver__'+args.suffix
    receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',args.candidate)
    negative=scratch/'negative'
    materialize_case(manifest,case,negative,source,args.candidate)
    (negative/'exception_context.json').unlink()
    failed=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',str(negative),
        '--output',str(negative/'analysis-report.json')],cwd=negative,env=execution_env(),
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'negative-analysis.log').write_text(failed.stdout)
    expected='Missing required source: exception_context.json'
    if failed.returncode==0 or expected not in failed.stdout:
        raise RuntimeError('Negative exact package failed to reject exception-source removal: '+failed.stdout)
    entry_negative=scratch/'entry-negative'
    materialize_case(manifest,case,entry_negative,source,args.candidate)
    (entry_negative/'entry-sources.json').unlink()
    entry_failed=subprocess.run([sys.executable,str(entry_negative/'finalize.py'),'--attempt',
        str(entry_negative),'--output',str(entry_negative/'analysis-report.json')],
        cwd=entry_negative,env=execution_env(),text=True,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'entry-negative-analysis.log').write_text(entry_failed.stdout)
    if entry_failed.returncode==0 or 'entry-sources.json' not in entry_failed.stdout:
        raise RuntimeError('Negative exact package failed to reject entry-source removal: '+entry_failed.stdout)
    park_negative=scratch/'park-negative'
    materialize_case(manifest,case,park_negative,source,args.candidate)
    park_controls=fixture.rows(park_negative/'native_controls.jsonl')
    park_controls[200]['hand_brake']=not park_controls[200]['hand_brake']
    fixture.write_rows(park_negative/'native_controls.jsonl',park_controls)
    park_failed=subprocess.run([sys.executable,str(park_negative/'finalize.py'),'--attempt',
        str(park_negative),'--output',str(park_negative/'analysis-report.json')],
        cwd=park_negative,env=execution_env(),text=True,
        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
    (scratch/'park-negative-analysis.log').write_text(park_failed.stdout)
    park_error='Parking source hash differs: native_controls.jsonl'
    if park_failed.returncode==0 or park_error not in park_failed.stdout:
        raise RuntimeError('Negative exact package failed to reject parking-control change: '+park_failed.stdout)
    if (park_negative/'result.json').exists():
        raise RuntimeError('Changed parking control emitted a result')
    print(json.dumps({'case_suffix':args.suffix,'candidate':args.candidate,
                      'positive':{k:v for k,v in receipt.items() if k!='fixture_manifest'},
                      'negative':{'exit_code':failed.returncode,'removed':'exception_context.json',
                                  'error_contains':expected},
                      'entry_negative':{'exit_code':entry_failed.returncode,
                          'removed':'entry-sources.json','error_contains':'entry-sources.json'},
                      'park_negative':{'exit_code':park_failed.returncode,
                          'changed':'native_controls.jsonl','error_contains':park_error},
                      'scope':'synthetic diagnostic v1; not selected or physical'}))


if __name__=='__main__':main()
