"""Full 480-frame source edits cross all three two-lane fallback thresholds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from two_lane_exception import two_lane_open_drive
from trigger_measure import SOURCES,extract,evaluate,rows,sha


def write_rows(path,items):
    path.write_text(''.join(json.dumps(item,sort_keys=True)+'\n' for item in items))


def refresh(root):
    names=('native_samples.jsonl','following_context.json','road.xodr')
    (root/'source-manifest.json').write_text(json.dumps({
        'format':'c102372-truck-follow-source-v1',
        'sha256':{name:sha(root/name) for name in names}},sort_keys=True)+'\n')
    (root/'trigger-source-manifest.json').write_text(json.dumps({
        'format':'c102372-truck-trigger-sources-v1',
        'sha256':{name:sha(root/name) for name in SOURCES}},sort_keys=True)+'\n')


def check(root,candidate,expected):
    metrics=extract(root,'two_lane_exception')
    path=root/'fallback-metrics.json'
    path.write_text(json.dumps(metrics,sort_keys=True)+'\n')
    if evaluate(candidate,metrics,path,sha(path),diagnostic=True) is not expected:
        raise AssertionError('Two-lane trigger threshold differs: '+candidate+' '+str(metrics))
    try:evaluate(candidate,metrics,path,sha(path))
    except ValueError as error:
        if 'not bound' not in str(error):raise
    else:raise AssertionError('Synthetic two-lane metrics accepted as original')
    try:evaluate(candidate,metrics,path,'0'*64,diagnostic=True)
    except ValueError as error:
        if 'hash differs' not in str(error):raise
    else:raise AssertionError('Wrong two-lane metric digest accepted')
    return metrics


def shift_lead(rows,shift):
    for row in rows:
        lead=row['lead'];lead['center_xy_m'][0]+=shift
        for point in lead['body_xy_m']:point[0]+=shift
        for point in lead['body_vertices_m']:point[0]+=shift


def main():
    os.environ['PATH']=str(ROOT/'.runtime-work/linux_arm64')+os.pathsep+os.environ.get('PATH','')
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-two-lane-triggers-') as temporary:
        root=Path(temporary)/'fixture'
        shutil.copytree(ROOT/'.runtime-work/c102372-saved-processing/probe_2-positive',root)
        (root/'road.xodr').write_text(two_lane_open_drive()+'\n')
        context=json.loads((root/'following_context.json').read_text())
        context['same_direction_lane_count']=2
        (root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
        camera=root/'camera_context.json'
        data=json.loads(camera.read_text());data['width']=640;data['height']=360
        camera.write_text(json.dumps(data,sort_keys=True)+'\n')
        (root/'overview.mkv').unlink()
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                        '-f','lavfi','-i','color=c=black:s=640x360:r=20:d=24',
                        '-frames:v','480','-c:v','ffv1',str(root/'overview.mkv')],
                       check=True,timeout=120)
        refresh(root)
        baseline=check(root,'fallback1',True)
        if baseline['min_surface_gap_m']>=152.4:raise AssertionError('Two-lane base gap differs')
        check(root,'fallback2',False)
        check(root,'fallback3',False)
        native=root/'native_samples.jsonl';original=native.read_bytes()
        items=rows(native);shift_lead(items,25)
        write_rows(native,items);refresh(root)
        wider=check(root,'fallback1',False)
        native.write_bytes(original);refresh(root)
        items=rows(native);shift_lead(items,-5)
        write_rows(native,items);refresh(root)
        short=check(root,'fallback2',True)
        native.write_bytes(original);refresh(root)
        items=rows(native)
        for row in items:row['overview_camera_pose']['yaw_deg']=60
        write_rows(native,items);refresh(root)
        off_frame=check(root,'fallback3',True)
        camera.write_text('tampered')
        try:extract(root,'two_lane_exception')
        except ValueError as error:
            if 'Trigger source missing or changed' not in str(error):raise
        else:raise AssertionError('Changed camera source accepted')
        return {'passed':True,'case':'two_lane_exception','frames':480,
            'fallback1':{'positive_gap_m':baseline['min_surface_gap_m'],
                         'negative_gap_m':wider['min_surface_gap_m']},
            'fallback2':{'negative_shortfall_m':baseline['max_gap_shortfall_m'],
                         'positive_shortfall_m':short['max_gap_shortfall_m']},
            'fallback3':{'negative_margin_px':baseline['min_projected_truck_frame_margin_px'],
                         'positive_margin_px':off_frame['min_projected_truck_frame_margin_px']},
            'changed_camera_source_rejected':True,'synthetic_as_original_rejected':True,
            'physical_or_accepted_claim':False}


if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
