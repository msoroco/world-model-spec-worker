"""Author source-shaped CPU diagnostics for the C125714 controlled policy pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def line(value):
    return json.dumps(value,separators=(',',':'))+'\n'


def body(x,y=-4):
    return [[x-.2,y-.2],[x+.2,y-.2],[x+.2,y+.2],[x-.2,y+.2]]


def build(label, ego_entry, policy):
    folder = ROOT/'cases'/label
    folder.mkdir(exist_ok=True)
    original = json.loads((ROOT/'diagnostic.json').read_text())
    files = original['files']
    case = BASE+'__'+label
    site = json.loads(files['site-context.json']);site['case_id']=case
    files['site-context.json']=line(site)
    prior = [json.loads(row) for row in files['ego-body-history.jsonl'].splitlines()]
    for i,row in enumerate(prior):
        row['body_vertices_xy_m']=body(-10 if i<ego_entry else
                                       (0 if label.startswith('yield') or i<72 else 10))
    files['ego-body-history.jsonl']=''.join(line(x) for x in prior)
    trace=[json.loads(row) for row in files['trace.jsonl'].splitlines()]
    events=[json.loads(row) for row in files['capture/evidence.jsonl'].splitlines()]
    for i,(t,event) in enumerate(zip(trace,events)):
        x=-10 if i<ego_entry else (0 if label.startswith('yield') or i<72 else 10)
        t['position']['x']=x;t['position_m'][0]=x
        event['ego']['position_m'][0]=x
        event['ego']['body_vertices_m']=[[px,py,z] for px,py in body(x) for z in (0,1.5)]
    files['trace.jsonl']=''.join(line(x) for x in trace)
    files['capture/evidence.jsonl']=''.join(line(x) for x in events)
    control=[]
    for i in range(75):
        brake=1.0 if (i<72 if policy=='wait_for_other_clear' else i<4) else 0.0
        control.append({'frame':i,'time_s':i/20,'ego_brake':brake,
                        'other_brake':1.0 if i<5 else 0.0,
                        'control_policy':policy,
                        'other_entered':i>=5,'other_cleared':i>=72})
    files['controller-history.jsonl']=''.join(line(x) for x in control)
    bindings={name:{'kind':'diagnostic_fixture','sha256':sha(files[name].encode())}
              for name in ('site-context.json','ego-body-history.jsonl',
                           'other-body-history.jsonl','controller-history.jsonl',
                           'video_frames.jsonl')}
    bindings['road.xodr']={'kind':'diagnostic_fixture',
                           'sha256':sha((ROOT/'candidate-map.xodr').read_bytes())}
    files['original-bindings.json']=line(bindings)
    files['acquisition.json']=line({name:{'kind':'diagnostic_fixture',
                                            'sha256':sha(value.encode())}
                                    for name,value in files.items()
                                    if name!='acquisition.json'})
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=case
    manifest['sources']['trace.jsonl']=sha(files['trace.jsonl'].encode())
    files['capture/manifest.json']=line(manifest)
    diagnostic=folder/'diagnostic.json'
    diagnostic.write_text(json.dumps(original,indent=2)+'\n')
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'road.xodr',
            'source':str((ROOT/'candidate-map.xodr').relative_to(Path.cwd())),
            'sha256':sha((ROOT/'candidate-map.xodr').read_bytes())}],
            'generator':{'source':str(diagnostic.relative_to(Path.cwd())),
                         'sha256':sha(diagnostic.read_bytes())}}
    (folder/'diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    return diagnostic, folder/'diagnostic-recipe.json'


if __name__=='__main__':
    build('yield_wait_for_other_clear',73,'wait_for_other_clear')
    build('advance_at_release',4,'advance_at_release')
