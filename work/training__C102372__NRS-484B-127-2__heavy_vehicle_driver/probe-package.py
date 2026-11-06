"""One exact unselected synthetic v1 Native/Core/Lean/video package probe."""
import argparse
import json
import os
from pathlib import Path
import pickle
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0,str(HERE/'native'))
from traffic_spec_adapter.adapter import load_graph
from worker_exchange.package_compatibility import run,materialize_case
from worker_exchange.runtime_cli import execution_env


def make_source(suffix,scratch):
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    source=scratch/'fixture'
    saved_suffix='probe_2' if suffix=='two_lane_exception' else suffix
    if suffix in ('conditions_steady','conditions_lead_brake'):
        shutil.copytree(ROOT/'.runtime-work/c102372-conditions-saved'/(suffix+'-positive'),source)
    elif suffix in ('passing_overtake','passing_hold'):
        folder='c102372-passing-saved' if suffix=='passing_overtake' else 'c102372-passing-hold-saved'
        shutil.copytree(ROOT/'.runtime-work'/folder/(suffix+'-positive'),source)
    else:
        shutil.copytree(ROOT/'.runtime-work/c102372-saved-processing'/(saved_suffix+'-positive'),source)
    for name in ('config.json','result.json','analysis-report.json'):(source/name).unlink()
    case=HERE.name+'__'+suffix
    manifest=HERE/'draft-execution-manifest.json'
    entry=next(item for item in json.loads(manifest.read_text())['cases'] if item['case_id']==case)
    ref=entry
    construction=json.loads((HERE/ref['construction']).read_text())
    config=json.loads(next(item['content'] for item in construction['files']
                           if item['path']=='config.json'))
    if suffix=='two_lane_exception':
        from two_lane_exception import two_lane_open_drive
        (source/'road.xodr').write_text(two_lane_open_drive()+'\n')
        context=source/'following_context.json';value=json.loads(context.read_text())
        value['same_direction_lane_count']=2
        context.write_text(json.dumps(value,sort_keys=True)+'\n')
        from measure_gap import sha as source_sha
        names=('native_samples.jsonl','following_context.json','road.xodr')
        (source/'source-manifest.json').write_text(json.dumps({
            'format':'c102372-truck-follow-source-v1',
            'sha256':{name:source_sha(source/name) for name in names}},sort_keys=True)+'\n')
    for camera in config['cameras']:
        name=camera['name'];path=source/(name+'.mkv');path.unlink()
        size=f"{camera['width']}x{camera['height']}"
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=24','-frames:v','480',
            '-c:v','ffv1',str(path)],check=True,timeout=120)
    camera_context=source/'camera_context.json'
    camera_data=json.loads(camera_context.read_text())
    camera_data['width']=1920;camera_data['height']=1080
    camera_context.write_text(json.dumps(camera_data,sort_keys=True)+'\n')
    if suffix in ('conditions_steady','conditions_lead_brake'):
        from conditions_trigger import extract
        (source/'fallback-metrics.json').write_text(json.dumps(extract(source,suffix),sort_keys=True)+'\n')
    elif suffix in ('passing_overtake','passing_hold'):
        if suffix=='passing_overtake':from passing_trigger import extract
        else:from passing_hold_trigger import extract
        (source/'fallback-metrics.json').write_text(json.dumps(extract(source),sort_keys=True)+'\n')
    else:
        from trigger_measure import SOURCES,sha as trigger_sha,extract
        trigger_manifest=source/'trigger-source-manifest.json'
        trigger_manifest.write_text(json.dumps({
            'format':'c102372-truck-trigger-sources-v1',
            'sha256':{name:trigger_sha(source/name) for name in SOURCES}},sort_keys=True)+'\n')
        (source/'fallback-metrics.json').write_text(json.dumps(extract(source,suffix),sort_keys=True)+'\n')
    (source/'capture/recorder_info.txt').write_text(
        'Create 107: vehicle.carlamotors.carlacola\nCreate 108: vehicle.carlamotors.carlacola\n')
    graph=load_graph(ROOT/'runtime/pipeline/fixtures/retained-speed/capture/native/graphs/base/00021714.pkl')
    folder=source/'capture/native/graphs/base';folder.mkdir(parents=True)
    rows=[]
    for index in range(480):
        frame=100+index;time=index/20
        graph.graph['frame']=frame
        (folder/f'{frame:08d}.pkl').write_bytes(pickle.dumps(graph,protocol=4))
        rows.append({'frame':frame,'time_s':time,'simulation_time':time,
            'base':f'graphs/base/{frame:08d}.pkl',
            'abstract':f'graphs/abstract/{frame:08d}.pkl','synthetic_diagnostic':True})
    (source/'capture/native/frames.jsonl').write_text(''.join(
        json.dumps(row)+'\n' for row in rows))
    capture=source/'capture/manifest.json';m=json.loads(capture.read_text())
    import hashlib
    for name in ('road.xodr','trace.jsonl'):
        m['sources'][name]=hashlib.sha256((source/name).read_bytes()).hexdigest()
    capture.write_text(json.dumps(m,sort_keys=True)+'\n')
    return source


def probe(suffix,candidate,source,scratch):
    case=HERE.name+'__'+suffix
    manifest=HERE/'draft-execution-manifest.json'
    output=scratch/'output'
    receipt=run(manifest,case,source,output,ROOT/'runtime/pipeline/library',
        ROOT/'.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
        candidate)
    negative=scratch/'negative';materialize_case(manifest,case,negative,source,candidate)
    (negative/'native_samples.jsonl').unlink()
    failed=subprocess.run([sys.executable,str(negative/'finalize.py'),'--attempt',
        str(negative),'--output',str(negative/'analysis-report.json')],cwd=negative,
        env=execution_env(),capture_output=True,text=True,timeout=300)
    if failed.returncode==0 or 'Missing required source: native_samples.jsonl' not in failed.stderr:
        raise ValueError('Exact package negative accepted: '+failed.stderr)
    return {'passed':True,'case':case,'candidate':candidate,
        'construction_sha256':receipt['construction_sha256'],'checks':receipt['checks'],
        'negative_exit_code':failed.returncode,'accepted_recording_claimed':False,
        'receipt':{key:value for key,value in receipt.items() if key!='fixture_manifest'},
        'negative_log':failed.stdout+failed.stderr}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=(
        'probe_1','probe_2','two_lane_exception','passing_overtake','passing_hold',
        'conditions_steady','conditions_lead_brake'),required=True)
    parser.add_argument('--candidate',choices=('primary','fallback1','fallback2','fallback3'),required=True)
    args=parser.parse_args()
    scratch=Path(tempfile.mkdtemp(dir=ROOT/'.runtime-work',prefix='c102372-package-'))
    source=make_source(args.case,scratch)
    return probe(args.case,args.candidate,source,scratch)


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
