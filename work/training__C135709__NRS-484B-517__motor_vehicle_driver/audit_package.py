"""Independently audit C135709 copied source, saved measurements and controls."""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

CASE=Path(__file__).resolve().parent
NATIVE=CASE/'native';ROOT=CASE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def run(bundle,script,args):
    return subprocess.run([sys.executable,str(bundle/script),*map(str,args)],
        capture_output=True,text=True,timeout=20)

def audit():
    manifest_path=CASE/'offline'/'manifest.json'
    proof_path=CASE/'offline'/'proof-compatibility.json'
    manifest=json.loads(manifest_path.read_text());proof=json.loads(proof_path.read_text())
    expected={(w,c) for w in ('reference','contrast')
              for c in ('primary','fallback1','fallback2','fallback3')}
    if (manifest['format']!='c135709-exact-offline-v1' or
        manifest['assignment_id']!=CASE.name or
        manifest['construction_sha256']!=sha(NATIVE/'manifest.json') or
        proof['manifest_sha256']!=sha(manifest_path) or
        len(proof['positives'])!=8 or len(proof['negatives'])!=32 or
        len(proof['saved_positives'])!=16 or len(proof['saved_negatives'])!=16 or
        manifest['delivery_ready'] or proof['delivery_ready']):
        raise ValueError('C135709 proof coverage differs')
    road=ET.parse(NATIVE/'stand-road.xodr').getroot()
    roads=road.findall('road')
    if len(roads)!=1 or roads[0].get('id')!='517':
        raise ValueError('C135709 road missing')
    objects=roads[0].findall('./objects/object')
    if (len(objects)!=2 or objects[0].get('name')!='TAXICAB STAND authored sign' or
        objects[1].get('type')!='parkingSpace'):
        raise ValueError('C135709 stand object differs')
    seen=set();frames=0;parked=0;checks=0;saved_checks=0;rejected=0;saved_rejected=0
    for entry in manifest['entries']:
        witness=entry['case_id'].removeprefix(CASE.name+'__')
        candidate=entry['candidate_id']
        if (witness,candidate) not in expected or (witness,candidate) in seen:
            raise ValueError('C135709 bundle coverage differs')
        seen.add((witness,candidate));bundle=CASE/entry['bundle']
        source=NATIVE/'drafts'/witness/candidate
        mapping={'config.json':source/'config.json',
            'requested-tracks.jsonl':source/'requested-tracks.jsonl',
            'stand-road.xodr':NATIVE/'stand-road.xodr',
            'measurement-contract.json':NATIVE/'measurement-contract.json',
            'check.py':NATIVE/'check.py','measure_saved.py':NATIVE/'measure_saved.py',
            'triggers.py':NATIVE/'triggers.py',
            'assignment-source.json':ROOT/'inputs'/CASE.name/'assignment.json',
            'case-plan.json':CASE/'case-plan.json'}
        for name in ('native-observed.jsonl','camera-frames.jsonl','stand-review.jsonl','stand-readback.json'):
            mapping['saved/'+name]=NATIVE/'saved-fixtures'/witness/candidate/name
        if (entry['sha256']!={name:sha(path) for name,path in mapping.items()} or
            entry['sha256']!={name:sha(bundle/name) for name in mapping}):
            raise ValueError('C135709 copied bytes differ')
        checked=run(bundle,'check.py',['--bundle',bundle])
        measured=run(bundle,'measure_saved.py',[bundle])
        if checked.returncode or measured.returncode:
            raise ValueError('C135709 copied execution failed')
        measure=json.loads(measured.stdout)
        req=rows(bundle/'requested-tracks.jsonl')
        obs=rows(bundle/'saved/native-observed.jsonl')
        cam=rows(bundle/'saved/camera-frames.jsonl')
        if not (len(req)==len(obs)==len(cam)==240) or measure['delivery_ready']:
            raise ValueError('C135709 saved coverage differs')
        full_body=0;stationary=0
        for i,(a,b,c) in enumerate(zip(req,obs,cam)):
            x,y=a['ego_x_m'],a['ego_y_m'];body=b['ego_body_xy_m']
            if (a['frame']!=b['frame'] or b['frame']!=c['frame'] or
                b['native_frame']!=c['camera_frame'] or
                b['ego_x_m']!=x or b['ego_y_m']!=y or
                b['ego_speed_mps']!=a['ego_speed_mps'] or
                b['lane_id']!=a['lane_id'] or
                body!=[[round(x+dx,6),round(y+dy,6)] for dx,dy in
                       ((2.3,.9),(2.3,-.9),(-2.3,.9),(-2.3,-.9))]):
                raise ValueError('C135709 independent saved frame differs')
            if b['ego_speed_mps']<=.1:
                stationary+=1
                if all(50<=p[0]<=75 and -8.25<=p[1]<=-3.5 for p in body):
                    full_body+=1
        if (measure['stationary_frames']!=stationary or
            measure['full_body_stand_occupied_frames']!=full_body):
            raise ValueError('C135709 independent parking count differs')
        parked+=full_body;frames+=240;checks+=1;saved_checks+=1
        routed=run(bundle,'triggers.py',[bundle])
        if routed.returncode or json.loads(routed.stdout)['delivery_ready']:
            raise ValueError('C135709 copied trigger differs')
        saved_checks+=1
        for name in ('requested-tracks.jsonl','assignment-source.json',
                     'stand-road.xodr','case-plan.json'):
            with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
                altered=Path(temporary)/'bundle';shutil.copytree(bundle,altered)
                path=altered/name;path.write_bytes(path.read_bytes()+b' ')
                if run(altered,'check.py',['--bundle',altered]).returncode==0:
                    raise ValueError('C135709 altered request source accepted')
                rejected+=1
        with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
            altered=Path(temporary)/'bundle';shutil.copytree(bundle,altered)
            path=altered/'saved/stand-readback.json'
            readback=json.loads(path.read_text());readback['sign_text']='BUS STOP'
            path.write_text(json.dumps(readback)+'\n')
            if run(altered,'measure_saved.py',[altered]).returncode==0:
                raise ValueError('C135709 altered stand sign accepted')
            saved_rejected+=1
            if run(altered,'triggers.py',[altered]).returncode==0:
                raise ValueError('C135709 altered trigger sign accepted')
            saved_rejected+=1
    if seen!=expected:raise ValueError('C135709 bundle set incomplete')
    receipt={'format':'c135709-independent-package-audit-v1',
        'manifest_sha256':sha(manifest_path),'proof_sha256':sha(proof_path),
        'bundles_checked':checks,'request_rows_recomputed':frames,
        'saved_rows_recomputed':frames,'stationary_stand_frames':parked,
        'request_negative_rejections_replayed':rejected,
        'saved_negative_rejections_replayed':saved_rejected,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline/package-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':print(json.dumps(audit()))
