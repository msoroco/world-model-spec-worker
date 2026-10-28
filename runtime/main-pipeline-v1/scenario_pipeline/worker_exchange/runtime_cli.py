"""One portable entrypoint around existing pipeline implementations.

No command allocates resources, starts a server, runs a law evaluator, or touches
campaign state. Capture runs only on explicit request against a supplied endpoint.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from .common import read, sha, within, write


def verify(runtime):
    runtime=Path(runtime)
    for rel, checksum in read(runtime/'SOURCE-MANIFEST.json')['files'].items():
        if sha(within(runtime,rel))!=checksum:raise ValueError('Runtime source changed: '+rel)
    return {'runtime_sources_verified':True}


def materialize(manifest, case_id, destination):
    """Materialize only a named inline construction; never select a campaign queue."""
    path=Path(manifest).resolve();manifest=read(path)
    matches=[c for c in manifest['cases'] if c['case_id']==case_id]
    if len(matches)!=1:raise ValueError('Select one exact case identity')
    declaration=matches[0]
    source=within(path.parent,declaration['construction'])
    if declaration.get('construction_sha256')!=sha(source):raise ValueError('Construction hash missing/changed')
    proposal=read(source)
    if proposal['case_id']!=case_id:raise ValueError('Construction/case identity differs')
    destination=Path(destination)
    if destination.exists():raise ValueError('Retain prior attempt; choose a new directory')
    destination.mkdir(parents=True)
    for entry in proposal['files']:
        target=within(destination,entry['path']);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(entry['content'])
    write(destination/'construction.json',proposal)
    return proposal



def execution_env():
    pipeline=Path(__file__).resolve().parents[1];runtime=pipeline.parent
    env=dict(os.environ)
    env['PYTHONPATH']=os.pathsep.join([str(pipeline),str(runtime/'python'),env.get('PYTHONPATH','')])
    return env


def offline(manifest,case_id,destination,python):
    proposal=materialize(manifest,case_id,destination)
    destination=Path(destination).resolve();entry=within(destination,proposal['entrypoint'])
    if not list((destination/'tests').glob('test*.py')):raise ValueError('Materialized bundle contains no tests')
    with (destination/'offline.log').open('w') as log:
        subprocess.run([python,str(entry),'--check'],cwd=destination,env=execution_env(),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
        subprocess.run([python,'-m','unittest','discover','-s','tests'],cwd=destination,env=execution_env(),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=300)
    return {'case_id':case_id,'offline_passed':True,'log':str(destination/'offline.log'),'simulation_started':False}

def capture(manifest,case_id,destination,host,port,python):
    proposal=materialize(manifest,case_id,destination)
    destination=Path(destination).resolve()
    entry=within(destination,proposal['entrypoint'])
    env=execution_env()
    subprocess.run([python,str(entry),'--check'],cwd=destination,env=env,check=True)
    # Caller must own the dedicated server. This wrapper never owns its lifecycle.
    subprocess.run([python,str(entry),'--output-dir',str(destination),'--host',host,'--port',str(port)],cwd=destination,env=env,check=True)
    return {'case_id':case_id,'attempt':str(destination),'capture_executed':True,'acceptance_claimed':False}


def process(attempt,output,library,validator=None):
    from traffic_spec_adapter.adapter import convert
    from traffic_spec_adapter.validate import validate_output
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    report=convert(attempt/'capture',attempt,Path(library),output)
    if validator:validate_output(output,validator)
    if report.get('required_measurements_complete') is not True:
        raise ValueError('Mandatory observation coverage incomplete: '+str(report.get('atom_coverage',{}).get('missing'))) 
    return {'converted':True,'output':str(output),'decoder_checked':bool(validator),'acceptance_claimed':False}


def render(attempt,converted,case):
    from review_recordings import render as existing_render
    attempt=Path(attempt).resolve();converted=Path(converted).resolve()
    # Existing renderer's documented input location; don't overwrite a prior trace.
    import shutil
    target=attempt/'traffic_spec'
    if target.exists() and target.resolve()!=converted:
        if sha(target/'trace.json')!=sha(converted/'trace.json'):raise ValueError('Existing render trace differs')
    elif not target.exists():shutil.copytree(converted,target)
    mapping=read_rows(attempt/'video_frames.jsonl')
    data={'review_source_video_frames':[0,len(mapping)-1],'review_source_window_s':[mapping[0]['time_s'],mapping[-1]['time_s']],
          'full_trace_frames':len(mapping),'full_recording_window_s':[mapping[0]['time_s'],mapping[-1]['time_s']],
          'speed_evaluation':None,'trace_coverage':{'kind':'full_recording'}}
    return existing_render(case,attempt,data)


def read_rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('selftest');a.add_argument('--runtime',default=str(Path(__file__).resolve().parents[2]));a.add_argument('--output',required=True);a.add_argument('--lake');a.add_argument('--validator');a.add_argument('--compare-to')
    a=sub.add_parser('compatibility-example');a.add_argument('--output',required=True)
    a=sub.add_parser('compatibility');a.add_argument('--manifest',required=True);a.add_argument('--case',required=True);a.add_argument('--fixture',required=True);a.add_argument('--output',required=True);a.add_argument('--library',required=True);a.add_argument('--validator',required=True)
    a=sub.add_parser('verify');a.add_argument('--runtime',type=Path,required=True)
    a=sub.add_parser('materialize');a.add_argument('--manifest',required=True);a.add_argument('--case',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('offline');a.add_argument('--manifest',required=True);a.add_argument('--case',required=True);a.add_argument('--output',required=True);a.add_argument('--python',default=sys.executable)
    a=sub.add_parser('validate-native');a.add_argument('--attempt',required=True);a.add_argument('--request',required=True);a.add_argument('--construction',required=True);a.add_argument('--exit-code',type=int,required=True)
    a=sub.add_parser('capture');a.add_argument('--manifest',required=True);a.add_argument('--case',required=True);a.add_argument('--output',required=True);a.add_argument('--host',required=True);a.add_argument('--port',required=True,type=int);a.add_argument('--python',default=sys.executable)
    a=sub.add_parser('process');a.add_argument('--attempt',required=True);a.add_argument('--output',required=True);a.add_argument('--library',required=True);a.add_argument('--validator')
    a=sub.add_parser('render');a.add_argument('--attempt',required=True);a.add_argument('--converted',required=True);a.add_argument('--case-json',required=True)
    a=sub.add_parser('validate-stage');a.add_argument('--stage',required=True);a.add_argument('--inputs',required=True);a.add_argument('--result',required=True);a.add_argument('--normalized')
    a=sub.add_parser('expand');a.add_argument('--proposal',required=True);a.add_argument('--templates',required=True);a.add_argument('--bindings',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('build-decoder');a.add_argument('--library',required=True);a.add_argument('--output',required=True);a.add_argument('--lake',required=True)
    args=p.parse_args()
    if args.command=='selftest':
        from .runtime_verify import run
        result=run(args.runtime,args.output,args.validator,args.lake,args.compare_to)
    elif args.command=='compatibility-example':
        from .compatibility_example import build
        m,c,f=build(Path(__file__).resolve().parents[2],args.output)
        result={'manifest':str(m),'case':c,'fixture':str(f),'scope':'software diagnostic only'}
    elif args.command=='compatibility':
        from .package_compatibility import run
        result=run(args.manifest,args.case,args.fixture,args.output,args.library,args.validator)
    elif args.command=='verify':result=verify(args.runtime)
    elif args.command=='materialize':result=materialize(args.manifest,args.case,args.output);result={'case_id':result['case_id'],'materialized':True}
    elif args.command=='offline':result=offline(args.manifest,args.case,args.output,args.python)
    elif args.command=='validate-native':
        from batch_pipeline.carla import validate_attempt
        result=validate_attempt(Path(args.attempt),read(args.request),read(args.construction),{'recorded_exit_code':args.exit_code},{})
    elif args.command=='capture':result=capture(args.manifest,args.case,args.output,args.host,args.port,args.python)
    elif args.command=='process':result=process(args.attempt,args.output,args.library,args.validator)
    elif args.command=='render':result=render(args.attempt,args.converted,read(args.case_json))
    elif args.command=='validate-stage':
        from batch_pipeline.stages import validate
        value=read(args.result);validate(args.stage,value,read(args.inputs))
        if args.normalized:write(args.normalized,value)
        result={'stage':args.stage,'valid':True,'simulation_started':False}
    elif args.command=='expand':
        from batch_pipeline.sweeps import expand_sweeps
        result=read(args.proposal);expand_sweeps(result,read(args.templates),read(args.bindings));write(args.output,result)
        result={'expanded_cases':len(result['cases']),'output':args.output}
    else:
        from traffic_spec_adapter.validate import build_validator
        result={'validator':str(build_validator(args.library,args.output,args.lake))}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
