"""Bind all eight unselected 3(a) CPU policies to exact source and map hashes."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
NATIVE=FOLDER/'native'
sys.path.insert(0,str(NATIVE))
from engineering import CANDIDATES,parameters
from trigger_evidence import TRIGGERS


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    batch=json.loads((ROOT/'batch.json').read_text())
    plan=json.loads((FOLDER/'case-plan.json').read_text())
    sources={name:sha(NATIVE/name) for name in
             ('geometry.py','controller.py','engineering.py','cameras.py','survey.py','trigger_evidence.py')}
    results=[]
    for case in ('controlled_1','controlled_2'):
        for candidate in CANDIDATES:
            p=parameters(case,candidate)
            encoded=json.dumps(p['authored_route_xy_m'],separators=(',',':')).encode()
            results.append({'case_id':plan['assignment_id']+'__'+case,
                            'candidate_id':candidate,
                            'authored_route_sha256':hashlib.sha256(encoded).hexdigest(),
                            'route_points':len(p['authored_route_xy_m']),
                            'purpose_request':p['purpose_request'],
                            'purpose_request_is_observation':False,
                            'entry_advance_m':p['entry_advance_m'],
                            'route_start_x_m':p['route_start_x_m'],
                            'controller_knobs':vars(p['controller_knobs']),
                            'camera_plan':p['camera_plan'],
                            'trigger':TRIGGERS.get(candidate),
                            'physical_success_claimed':False})
    data={'format':'c394300-3a-unselected-cpu-construction-policies-v1',
          'assignment_id':plan['assignment_id'],'law_text_sha256':plan['source_law']['text_sha256'],
          'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
          'map_sha256':sha(FOLDER/'draft-construction/scene.xodr'),
          'source_sha256':sources,'status':'unselected_prebundle',
          'exact_pinned_offline_passed':False,'portable_compatibility_passed':False,
          'cases':results}
    target=FOLDER/'draft-construction/candidate-manifest.json'
    target.write_text(json.dumps(data,indent=2)+'\n')
    return {'passed':True,'candidate_rows':len(results),'manifest_sha256':sha(target),
            'offline_or_delivery_claimed':False}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
