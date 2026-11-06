"""Controlled full-resolution source edits prove each C102372 fallback threshold."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from trigger_measure import SOURCES,extract,evaluate,sha,rows

spec=importlib.util.spec_from_file_location('package',HERE/'probe-package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)


def write_rows(path,items):path.write_text(''.join(
    json.dumps(item,sort_keys=True)+'\n' for item in items))


def refresh(root):
    manifest=root/'source-manifest.json'
    data=json.loads(manifest.read_text())
    for name in data['sha256']:data['sha256'][name]=sha(root/name)
    manifest.write_text(json.dumps(data,sort_keys=True)+'\n')
    path=root/'trigger-source-manifest.json'
    path.write_text(json.dumps({'format':'c102372-truck-trigger-sources-v1',
        'sha256':{name:sha(root/name) for name in SOURCES}},sort_keys=True)+'\n')


def check(root,case,candidate,expected):
    metrics=extract(root,case)
    path=root/'fallback-metrics.json';path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
    result=evaluate(candidate,metrics,path,sha(path),diagnostic=True)
    if result is not expected:raise AssertionError((case,candidate,metrics))
    try:evaluate(candidate,metrics,path,sha(path))
    except ValueError as exc:
        if 'not bound' not in str(exc):raise
    else:raise AssertionError('Synthetic truck trigger accepted as original')
    try:evaluate(candidate,metrics,path,'0'*64,diagnostic=True)
    except ValueError as exc:
        if 'hash differs' not in str(exc):raise
    else:raise AssertionError('Wrong source metric digest accepted')
    return metrics


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-trigger-proof-') as temporary:
        scratch=Path(temporary)
        for suffix in ('probe_1','probe_2'):(scratch/suffix).mkdir()
        first=package.make_source('probe_1',scratch/'probe_1')
        second=package.make_source('probe_2',scratch/'probe_2')
        one=check(first,'probe_1','fallback1',False)
        two=check(second,'probe_2','fallback1',True)
        baseline=check(first,'probe_1','fallback2',False)
        check(first,'probe_1','fallback3',False)
        original=(first/'native_samples.jsonl').read_bytes()
        original_manifest=(first/'source-manifest.json').read_bytes()
        original_trigger=(first/'trigger-source-manifest.json').read_bytes()
        native=rows(first/'native_samples.jsonl')
        for index,row in enumerate(native):
            shift=min(index,100)*.05
            lead=row['lead'];lead['center_xy_m'][0]-=shift
            for point in lead['body_xy_m']:point[0]-=shift
            for point in lead['body_vertices_m']:point[0]-=shift
            lead['speed_mps']=7. if 0<index<=100 else 8.
        write_rows(first/'native_samples.jsonl',native);refresh(first)
        shorter=check(first,'probe_1','fallback2',True)
        (first/'native_samples.jsonl').write_bytes(original)
        (first/'source-manifest.json').write_bytes(original_manifest)
        (first/'trigger-source-manifest.json').write_bytes(original_trigger)
        native=rows(first/'native_samples.jsonl')
        for row in native:row['overview_camera_pose']['yaw_deg']=60.
        write_rows(first/'native_samples.jsonl',native);refresh(first)
        off_frame=check(first,'probe_1','fallback3',True)
        (first/'camera_context.json').write_text('tampered')
        try:extract(first,'probe_1')
        except ValueError as exc:
            if 'Trigger source missing or changed' not in str(exc):raise
        else:raise AssertionError('Altered overview camera source accepted')
        return {'passed':True,'source_kind':'synthetic_cpu_fixture',
            'fallback1':{'negative_gap_m':one['min_surface_gap_m'],
                         'positive_gap_m':two['min_surface_gap_m']},
            'fallback2':{'negative_shortfall_m':baseline['max_gap_shortfall_m'],
                         'positive_shortfall_m':shorter['max_gap_shortfall_m']},
            'fallback3':{'negative_margin_px':baseline['min_projected_truck_frame_margin_px'],
                         'positive_margin_px':off_frame['min_projected_truck_frame_margin_px']},
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
