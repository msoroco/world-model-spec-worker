"""Run current saved-processing on source-only synthetic motorcycle acquisition.

This diagnostic never represents a Native capture or operator owner release.
"""
import hashlib
import argparse
import importlib.util
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE_PREFIX='training__C110919__NRS-484B-307-8d__motorcycle_or_moped_operator__selected_109a5dbc__'
MANIFEST=HERE/'saved-diagnostic-manifest.json'
LIBRARY=ROOT/'runtime/pipeline/library'
VALIDATOR=ROOT/'.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path,items):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(item,separators=(',',':'))+'\n' for item in items))


def build_attempt(destination, condition):
    spec=importlib.util.spec_from_file_location('saved_fixture',HERE/'saved-fixture-proof.py')
    fixture=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    fixture.make_attempt(destination,condition)
    manifest=json.loads(MANIFEST.read_text())
    entry=next(item for item in manifest['cases'] if item['case_id']==CASE_PREFIX+condition)
    construction=json.loads((HERE/entry['construction']).read_text())
    (destination/'construction.json').write_text(json.dumps(construction,indent=2)+'\n')
    for item in construction['files']:
        target=destination/item['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(item['content'])
    if (destination/'channels').exists() or (destination/'context.json').exists():
        raise ValueError('Fixture prepopulates derived observations')
    shutil.copyfile(HERE/'native/road.xodr',destination/'road.xodr')
    native=rows(destination/'native_samples.jsonl')
    mapping=rows(destination/'video_frames.jsonl')
    if len(native)!=600 or len(mapping)!=600:
        raise ValueError('Expected 600 acquisition rows')
    graphs=[]
    for sample,item in zip(native,mapping):
        frame=sample['native_frame'];time=sample['time_s']
        x,y=sample['native_center_xy_m'];heading=sample['native_yaw_deg']
        graph={'format':'native-adapter-graph-v1','multigraph':False,
               'metadata':{'frame':frame,'simulation_time_s':time},
               'nodes':[{'id':'ego','attributes':{'vertex':[x,y,.5],
                         'sem_class':'ego','forward':[math.cos(math.radians(heading)),
                         math.sin(math.radians(heading)),0.0],
                         'entity_id':107,'carla_speed':sample['speed_mps'],
                         'special_class':'ego'}}], 'edges':[]}
        rel=f'graphs/base/{frame:08d}.adapter.json'
        graph_path=destination/'capture/native'/rel
        graph_path.parent.mkdir(parents=True,exist_ok=True)
        graph_path.write_text(json.dumps(graph,separators=(',',':'))+'\n')
        graphs.append({'frame':frame,'simulation_time':time,'time_s':time,
                       'adapter_graph':rel,'synthetic_diagnostic':True})
    write_rows(destination/'capture/native/frames.jsonl',graphs)
    capture_manifest=json.loads((destination/'capture/manifest.json').read_text())
    capture_manifest['sources']={'road.xodr':sha(destination/'road.xodr'),
                                 'trace.jsonl':sha(destination/'trace.jsonl')}
    (destination/'capture/manifest.json').write_text(json.dumps(capture_manifest)+'\n')
    for name in ('overview','approach','signal','destination'):
        (destination/(name+'.mkv')).unlink()
    dimensions={'overview':'1920x1080','approach':'1280x720',
                'reference_corner':'1280x720','driver_reference':'1280x720'}
    for name,size in dimensions.items():
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-f','lavfi','-i',f'color=c=black:s={size}:r=20:d=30',
                        '-frames:v','600','-c:v','ffv1',str(destination/(name+'.mkv'))],
                       check=True,timeout=600)
    return {'attempt':str(destination),'construction_sha256':sha(destination/'construction.json'),
            'source_video_sha256':{name:sha(destination/(name+'.mkv')) for name in dimensions},
            'source_frames':600,'original_native_observed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--condition',choices=('condition_a','condition_b'),default='condition_a')
    condition=parser.parse_args().condition
    case=CASE_PREFIX+condition
    if not VALIDATOR.is_file():
        raise ValueError('Current validator absent')
    scratch=Path(tempfile.mkdtemp(prefix='c110919-process-saved-',dir=ROOT/'.runtime-work'))
    attempt=scratch/'attempt'
    source=build_attempt(attempt,condition)
    output=scratch/'processed'
    command=[sys.executable,str(ROOT/'runtime.py'),'process-saved',
             '--manifest',str(MANIFEST),'--case',case,'--attempt',str(attempt),
             '--output',str(output),'--library',str(LIBRARY),
             '--validator',str(VALIDATOR)]
    run=subprocess.run(command,text=True,stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT,timeout=1800)
    suffix='-b' if condition=='condition_b' else ''
    log=HERE/('native/current-process-saved-command'+suffix+'.log')
    log.write_text(run.stdout)
    if run.returncode:
        raise RuntimeError(f'Current process-saved failed (exit {run.returncode}); see command log; scratch {scratch}')
    receipt=json.loads(run.stdout)
    if not receipt.get('passed') or receipt.get('missing_evidence') or not receipt.get('originals_preserved'):
        raise ValueError('Saved processing did not produce a complete positive diagnostic')
    result={'format':'c110919-current-process-saved-diagnostic-v1',
            'passed':True,'case_id':case,'manifest_sha256':sha(MANIFEST),
            'source':source,'processing_receipt':receipt,
            'command_log_sha256':sha(log),
            'original_native_observed':False,'selected_delivery':False,
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    target=HERE/('native/current-process-saved-proof'+suffix+'.json')
    target.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'proof_sha256':sha(target),'scratch':str(scratch)}))


if __name__=='__main__':
    main()
