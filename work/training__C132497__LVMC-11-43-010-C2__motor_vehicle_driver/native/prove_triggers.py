"""Exercise measured fallback decisions and a corrupt frame join."""
import json
from pathlib import Path
import shutil
import tempfile

import triggers

CASE=Path(__file__).resolve().parent.parent

def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write(path,items):Path(path).write_text(''.join(json.dumps(x)+'\n' for x in items))

def prove():
    bundle=CASE/'offline'/'bundles'/'reference'/'primary'
    base=triggers.route(bundle)
    if base['triggered']!={'fallback1':False,'fallback2':False,'fallback3':True}:
        raise ValueError('C132497 base triggers differ')
    dwell_bundle=CASE/'offline'/'bundles'/'reference'/'fallback3'
    dwell=triggers.route(dwell_bundle)
    if (dwell['first_40_stopped_frames']!=40 or
            dwell['triggered']['fallback3'] is not False):
        raise ValueError('C132497 complete-route dwell fallback did not resolve its trigger')
    with tempfile.TemporaryDirectory() as temporary:
        saved=Path(temporary)/'saved';shutil.copytree(bundle/'saved',saved)
        path=saved/'camera-frames.jsonl';camera=rows(path)
        for frame in camera[:40]:frame['right_lane_visible']=False
        write(path,camera);elevated=triggers.route(bundle,saved)
        if elevated['first_40_visible_frames']!=0 or not elevated['triggered']['fallback2']:
            raise ValueError('C132497 visibility trigger differs')
        shutil.rmtree(saved);shutil.copytree(bundle/'saved',saved)
        path=saved/'native-observed.jsonl';observed=rows(path)
        i=next(i for i,row in enumerate(observed) if row['phase']=='circulation')
        observed[i]['ego_y_m']-=.3
        write(path,observed);slow=triggers.route(bundle,saved)
        if not slow['triggered']['fallback1'] or slow['maximum_lane_center_deviation_m']<=.2:
            raise ValueError('C132497 lane deviation trigger differs')
        camera=rows(saved/'camera-frames.jsonl');camera[i]['camera_frame']+=1
        write(saved/'camera-frames.jsonl',camera)
        try:triggers.route(bundle,saved)
        except ValueError:negative=True
        else:raise ValueError('C132497 altered trigger camera join accepted')
    result={'format':'c132497-trigger-proof-v1',
        'base':base,'dwell_variant':dwell,
        'visibility_variant':elevated,'lane_deviation_variant':slow,
        'changed_camera_join_rejected':negative,'synthetic_only':True,
        'delivery_ready':False}
    (CASE/'offline'/'proof-triggers.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=prove();print(json.dumps({'base':p['base']['triggered'],
        'visibility':p['visibility_variant']['triggered'],
        'deviation':p['lane_deviation_variant']['triggered'],
        'negative':p['changed_camera_join_rejected']}))
