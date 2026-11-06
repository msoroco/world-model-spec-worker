"""Exercise frozen CPU Core/Lean/render on one exact synthetic C104538 case."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
DEST=REPO/'.runtime-work/c104538/core-diagnostic-v2/below_500_ft'
CASE=ROOT.name+'__below_500_ft'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def call(label,command,env):
    run=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,timeout=300)
    log=ROOT/'core-diagnostic-logs'/(label+'.log');log.parent.mkdir(exist_ok=True)
    log.write_text(run.stdout+run.stderr)
    return run,log

def run():
    if DEST.exists():raise ValueError('Retain prior Core diagnostic')
    env=dict(os.environ)
    env['PATH']=str(REPO/'.runtime-work/linux_arm64')+os.pathsep+env.get('PATH','')
    env['LD_LIBRARY_PATH']=str(REPO/'.runtime-work/geos-wheel/shapely.libs')
    build,build_log=call('build',['.venv-cpu/bin/python',str(ROOT/'build-core-diagnostic.py')],env)
    if build.returncode:raise ValueError(build.stderr[-2000:])
    provenance=json.loads(build.stdout)
    fixture=DEST/'positive'
    validator=REPO/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck'
    if not validator.is_file():raise ValueError('Pinned local Lean decoder unavailable')
    process,process_log=call('positive-process',['.venv-cpu/bin/python',str(REPO/'runtime.py'),
        'process','--attempt',str(fixture),'--output',str(fixture/'converted'),
        '--library',str(REPO/'runtime/pipeline/library'),'--validator',str(validator)],env)
    if process.returncode:raise ValueError(process.stderr[-2000:])
    render,render_log=call('positive-render',['.venv-cpu/bin/python',str(REPO/'runtime.py'),
        'render','--attempt',str(fixture),'--converted',str(fixture/'converted'),
        '--case-json',str(fixture/'case.json')],env)
    if render.returncode:raise ValueError(render.stderr[-2000:])
    negative=DEST/'negative_missing_native_frames'
    shutil.copytree(fixture,negative,ignore=shutil.ignore_patterns(
        'converted','traffic_spec','event_review*','review*','synthetic-480.mkv'))
    (negative/'capture/native/frames.jsonl').unlink()
    failed,negative_log=call('negative-missing-native-frames',['.venv-cpu/bin/python',
        str(REPO/'runtime.py'),'process','--attempt',str(negative),
        '--output',str(negative/'converted'),'--library',str(REPO/'runtime/pipeline/library'),
        '--validator',str(validator)],env)
    if failed.returncode==0 or 'capture/native/frames.jsonl' not in failed.stderr:
        raise ValueError('Missing Native frames negative did not reject as specified')
    report=json.loads((fixture/'converted/adapter_report.json').read_text())
    review=json.loads((fixture/'event_review.json').read_text())
    if (report['required_measurements_complete'] is not True or
        review['frames']!=480 or review['coverage_kind']!='full_delivered_trace'):
        raise ValueError('Core or review did not cover all 480 frames')
    output={'format':'c104538-synthetic-core-diagnostic-v1','case_id':CASE,
        'synthetic':True,'selected':False,'accepted':False,'physical_visibility_proven':False,
        'frames':480,'provenance':provenance,
        'pinned_runtime_manifest_sha256':sha(REPO/'runtime/pipeline/SOURCE-MANIFEST.json'),
        'lean_decoder_sha256':sha(validator),
        'core_trace_sha256':sha(fixture/'converted/trace.json'),
        'adapter_report_sha256':sha(fixture/'converted/adapter_report.json'),
        'review_receipt_sha256':sha(fixture/'event_review.json'),
        'review_video_sha256':sha(fixture/'event_review.webm'),
        'review_frame_map_sha256':sha(fixture/'event_review_frames.jsonl'),
        'logs':{label:{'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
                for label,path in [('build',build_log),('positive_process',process_log),
                                   ('positive_render',render_log),('negative_missing_native_frames',negative_log)]},
        'negative_exit_code':failed.returncode,
        'scope':'repeated pinned graph and generated black video software integration; no exact authored road, Native physical behavior, original pixels, accepted recording, or strict package compatibility'}
    (ROOT/'core-diagnostic-summary.json').write_text(json.dumps(output,indent=2)+'\n')
    return {'case_id':CASE,'core_frames':480,'render_frames':480,'negative_rejected':True,
            'accepted':False}

if __name__=='__main__':print(json.dumps(run()))
