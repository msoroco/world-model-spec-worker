"""Bind exact Native motion sources and a clear-junction controller to every case."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'stop-reference-construction-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def upgrade(construction,root=False):
    for item in construction['files']:
        if item['path']=='config.json':
            cfg=json.loads(item['content'])
            cfg['duration_s']=30
            cfg['physical_completion']={
                'criterion':'intersection_clearance',
                'motion_source':'native-raw-actors.jsonl',
                'body_key':'ego.body_native_xyz_m',
                'context_sources':['native-map-readback.json'],
                'intersection_polygon_xy_m':[[-20,-20],[20,-20],[20,20],[-20,20]],
                'exit_axis':0,'exit_sign':1,'minimum_progress_m':30,
                'completion_goal_method':'Whole ego body clears the authored junction polygon in original Native samples; engineering completion only.'}
            for camera,(width,height) in zip(cfg['cameras'],
                                             ((1920,1080),(1280,720),(1280,720),(1280,720))):
                camera.update(width=width,height=height,fov_deg=80,
                              pose_strategy='fixed junction view, original frame join')
            item['content']=json.dumps(cfg,indent=2,sort_keys=True)+'\n'
        if item['path']=='capture_selected.py':
            source=item['content']
            before="target = 0 if phase == 'hold_pre_line' else 1.0 if phase == 'approach' else 2.0"
            alternate="target = 0 if phase == 'hold_pre_line' else 1.0 if phase == 'approach' else 4.0 if other else 2.0"
            replacement="target = 0 if phase == 'hold_pre_line' else 1.0 if phase == 'approach' else 4.0"
            if before in source:source=source.replace(before,replacement)
            elif alternate in source:source=source.replace(alternate,replacement)
            elif replacement not in source:raise ValueError('Unexpected Native controller')
            item['content']=source
    return construction


manifest=json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    for name,target in (('primary',entry),('fallback1',entry['candidates'][0])):
        path=ROOT/target['construction']
        construction=upgrade(json.loads(path.read_text()))
        write(path,construction)
        target['construction_sha256']=sha(path)
        for key in ('offline','compatibility','saved_processing'):
            target.pop(key,None)
        if name=='primary':
            for key in ('negative','post_capture','delivery_acceptance'):
                entry.pop(key,None)
    entry['kind']='draft_not_selected'
manifest['status']='native_motion_source_reproof_in_progress'
write(MANIFEST,manifest)
root=ROOT/'construction.json'
construction=upgrade(json.loads(root.read_text()),root=True)
write(root,construction)
for item in construction['files']:
    path=ROOT/item['path']
    if path.exists():path.write_text(item['content'])
