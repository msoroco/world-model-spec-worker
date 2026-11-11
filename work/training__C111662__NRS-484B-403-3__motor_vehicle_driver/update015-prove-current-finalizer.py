"""Exercise each current C111662 primary finalizer on retained synthetic raw sources."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT/'native'
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.measurement_contract import validate, verify_report


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(case, candidate, destination):
    manifest = ROOT/'draft-execution-manifest.json'
    materialize(manifest, ROOT.name+'__'+case, destination, candidate)
    if case.startswith('divided_'):
        raw = NATIVE/'divided-opening'/'synthetic'/case/candidate/'raw.json'
    else:
        raw = NATIVE/'synthetic'/case/candidate/'raw.json'
    if not raw.is_file():
        raise ValueError('Missing retained synthetic raw source: '+str(raw))
    shutil.copyfile(raw,destination/'raw.json')
    source = json.loads(raw.read_text())
    with (destination/'trace.jsonl').open('w') as trace, (destination/'video_frames.jsonl').open('w') as mapping:
        for row in source['rows']:
            index,time = row['frame'],row['time_s']
            pose = row['ego']
            trace.write(json.dumps({'frame':index,'time_s':time,
                                    'position_m':pose['center_xyz_m'],
                                    'heading_deg':pose['heading_rad']*180/3.141592653589793})+'\n')
            mapping.write(json.dumps({'video_frame':index,'carla_frame':index,
                                      'native_frame':index,'time_s':time})+'\n')
    return raw


def run():
    manifest = json.loads((ROOT/'draft-execution-manifest.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    workspace = REPO/'.runtime-work'/'update015-c111662-current-finalizer-matrix'
    workspace.mkdir(parents=True,exist_ok=True)
    results=[]
    for entry in manifest['cases']:
      for candidate in ('primary','fallback1','fallback2','fallback3'):
        case = entry['case_id'].rsplit('__',1)[-1]
        attempt = workspace/case/candidate
        if attempt.exists(): shutil.rmtree(attempt)
        raw = prepare(case,candidate,attempt)
        code = NATIVE/'finalize_current.py'
        contract = json.loads((ROOT/entry['measurement_contract']).read_text())
        validate(contract,plan['requirement_dispositions'],code.read_text(),entry['case_id'])
        command = [sys.executable,str(attempt/'finalize_current.py'),
                   '--attempt',str(attempt),'--output',str(attempt/'analysis-report.json')]
        result = subprocess.run(command,cwd=REPO,env=execution_env(),capture_output=True,text=True)
        (ROOT/f'update015-{case}-{candidate}-finalizer-positive.log').write_text(result.stdout+result.stderr)
        if result.returncode:
            raise ValueError(f'{case}/{candidate} finalizer failed: {result.stderr[-2000:]}')
        report = json.loads((attempt/'analysis-report.json').read_text())
        measurements = verify_report(contract,report,attempt)
        missing = workspace/case/(candidate+'-missing-raw')
        if missing.exists(): shutil.rmtree(missing)
        prepare(case,candidate,missing)
        (missing/'raw.json').unlink()
        failure = subprocess.run([sys.executable,str(missing/'finalize_current.py'),
                                  '--attempt',str(missing),
                                  '--output',str(missing/'analysis-report.json')],
                                 cwd=REPO,env=execution_env(),capture_output=True,text=True)
        (ROOT/f'update015-{case}-{candidate}-finalizer-negative.log').write_text(failure.stdout+failure.stderr)
        expected = contract['negative']['error_contains']
        if failure.returncode==0 or expected not in failure.stderr:
            raise ValueError(f'{case}/{candidate} missing raw source was not rejected')
        results.append({'case_id':entry['case_id'],'candidate_id':candidate,
                        'positive_passed':True,'missing_raw_rejected':True,
                        'raw_sha256':sha(raw),'analysis_sha256':sha(attempt/'analysis-report.json'),
                        'result_sha256':sha(attempt/'result.json'),
                        'measurement_keys':sorted(measurements),
                        'scope':'finalizer-only synthetic diagnostic; no Native/Core/Lean/video compatibility'})
    output = ROOT/'update015-current-finalizer-matrix.json'
    output.write_text(json.dumps({'format':'c111662-current-finalizer-matrix-v1',
                                  'results':results},indent=2)+'\n')
    print(json.dumps({'candidate_positive':len(results),'missing_source_negative':len(results)},sort_keys=True))


if __name__=='__main__':run()
