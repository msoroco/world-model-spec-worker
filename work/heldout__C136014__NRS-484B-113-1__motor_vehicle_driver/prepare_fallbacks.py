"""Build three same-case alternate inline constructions for local review."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parent
primary=json.loads((ROOT/'construction.json').read_text())

def change(construction,path,old,new):
    entry=next(f for f in construction['files'] if f['path']==path)
    if old not in entry['content']:raise ValueError('Expected source phrase changed: '+old)
    entry['content']=entry['content'].replace(old,new)
    entry.pop('source',None)

for candidate in ('fallback1','fallback2','fallback3'):
    source=json.loads(json.dumps(primary))
    if candidate=='fallback1':
        change(source,'runner.py','waypoint.previous(18.0)','waypoint.previous(16.0)')
        change(source,'tests/test_runner.py',"self.assertEqual(scene['other'].transform.location.x,-18)","self.assertEqual(scene['other'].transform.location.x,-16)")
    elif candidate=='fallback2':
        change(source,'runner.py','throttle=.22,reverse=True','throttle=.14,reverse=True')
    else:
        change(source,'backing_camera_capture.py','"approach": ((1.2, 0.0, 2.0)',
               '"approach": ((1.8, 0.0, 2.4)')
    folder=ROOT/'cases';folder.mkdir(exist_ok=True)
    (folder/(candidate+'-construction.json')).write_text(json.dumps(source,indent=2)+'\n')
