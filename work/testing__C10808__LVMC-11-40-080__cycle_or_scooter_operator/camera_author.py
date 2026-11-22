"""Bind the exact four-view capture plan into both C10808 configurations."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'execution-manifest.json'
SIZES=(('overview',1920,1080),('approach',1280,720),
       ('reference_corner',1280,720),('driver_reference',1280,720))
POSES={
    'overview':'operator-attached high oblique view of alley and turn sign',
    'approach':'operator-attached oblique approach and sign view',
    'reference_corner':'operator-attached corner view of turn and sign',
    'driver_reference':'operator-attached low forward reference view'}


def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path=ROOT/'case-plan.json';plan=json.loads(plan_path.read_text())
    plan['camera_plan']={'profile':'overview1080-capability','duration_s':30,
        'composition':'synchronized_four_view_primary',
        'coverage':[
            {'subject':'prohibited-turn sign, operator, bicycle and full alley turn',
             'interval':'full 30 s original capture','view':'overview'},
            {'subject':'sign approach, rider contact and dismount onset',
             'interval':'approach through turn start','view':'approach'},
            {'subject':'sign face, operator and bicycle separation through reversal',
             'interval':'dismount hold or mounted reversal through turn completion',
             'view':'reference_corner'},
            {'subject':'original operator-forward reference during approach and turn',
             'interval':'full 30 s original capture','view':'driver_reference'}]}
    write(plan_path,plan)
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        path=ROOT/entry['construction'];construction=json.loads(path.read_text())
        for file in construction['files']:
            if file['path']=='config.json':
                config=json.loads(file['content'])
                config['cameras']=[{'name':name,'width':width,'height':height,
                    'pose_strategy':POSES[name],'fov_deg':90}
                    for name,width,height in SIZES]
                file['content']=json.dumps(config,indent=2)+'\n'
                if entry['case_id'].endswith('__dismount_before_uturn'):
                    (ROOT/'config.json').write_text(file['content'])
                break
        else:raise ValueError('Exact construction lacks config.json')
        write(path,construction);entry['construction_sha256']=sha(path)
    write(MANIFEST,manifest)


if __name__=='__main__':main()
