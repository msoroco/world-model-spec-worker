"""Three same-case physical-risk alternatives for each expanded backing case."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent
manifest_path=ROOT/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for entry in manifest['cases'][1:]:
    base=json.loads((ROOT/entry['construction']).read_text());slug=entry['case_id'].split('__')[-1]
    root=ROOT/'cases'/slug
    offset=10 if slug=='reverse_close_traffic_steady' else 18
    for i in (1,2,3):
        candidate=json.loads(json.dumps(base))
        def change(path,old,new):
            f=next(f for f in candidate['files'] if f['path']==path)
            if old not in f['content']:raise ValueError('Expected phrase changed: '+old)
            f['content']=f['content'].replace(old,new);f.pop('source',None)
        if i==1:
            change('runner.py',f'waypoint.previous({offset}.0)',f'waypoint.previous({offset-2}.0)')
            change('tests/test_runner.py',f"self.assertEqual(scene['other'].transform.location.x,-{offset})",
                   f"self.assertEqual(scene['other'].transform.location.x,-{offset-2})")
        elif i==2:change('runner.py','throttle=.22,reverse=True','throttle=.14,reverse=True')
        else:change('backing_camera_capture.py','"approach": ((1.2, 0.0, 2.0)',
                    '"approach": ((1.8, 0.0, 2.4)')
        p=root/(f'fallback{i}-construction.json');p.write_text(json.dumps(candidate,indent=2)+'\n')
        if i==1:
            trigger={'source':'Native waypoint selection diagnostic','metric':'connected rear spawn candidates',
                     'failure_condition':f'Primary {offset} m rear continuation absent; use {offset-2} m verified continuation'}
            knobs=[f'rear actor spawn offset {offset} m to {offset-2} m']
        elif i==2:
            trigger={'source':'original backing_history.jsonl actor positions','metric':'closing rate and minimum center distance',
                     'failure_condition':'Primary reverse control enters 2 m engineering collision-risk band before planned stop'}
            knobs=['ego reverse throttle 0.22 to 0.14']
        else:
            trigger={'source':'full decoded original approach RGB source','metric':'per-frame complete body visibility',
                     'failure_condition':'Subject or other vehicle body omitted from any original approach frame'}
            knobs=['approach camera mount x 1.2 to 1.8 m, z 2.0 to 2.4 m']
        entry['candidates'].append({'id':f'fallback{i}','construction':str(p.relative_to(ROOT)),
            'construction_sha256':sha(p),'trigger':trigger,'changed_knobs':knobs})
    entry['candidate_risk']={'status':'physical','reason':'Native map route, reverse control and original-camera coverage may independently fail'}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
