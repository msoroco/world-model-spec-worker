"""Pinned offline and survey proofs for the visible vehicle-movement draft."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CASE=HERE.name+'__preparing_movement'
CANDIDATES=(('primary',-20),('fallback1',-25),('fallback2',-20))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    scratch_root=REPO/'.runtime-work'
    scratch_root.mkdir(exist_ok=True)
    manifest=HERE/'draft-preparing-movement-manifest.json'
    manifest_sha=sha(manifest)
    results=[]
    with tempfile.TemporaryDirectory(prefix='c404492-preparing-',dir=scratch_root) as tmp:
        for candidate,gap in CANDIDATES:
            out=Path(tmp)/candidate
            command=[sys.executable,str(REPO/'runtime.py'),'offline',
                     '--manifest',str(manifest),'--case',CASE,'--candidate',candidate,
                     '--output',str(out),'--python',sys.executable]
            run=subprocess.run(command,capture_output=True,text=True,check=True,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
                     'SCENARIO_PIPELINE_OUTPUT_ROOT':str(scratch_root/'c404492-preparing-proof')})
            if json.loads(run.stdout).get('offline_passed') is not True:
                raise ValueError('Pinned offline result not passed')
            runner_path=out/'runner.py'
            spec=importlib.util.spec_from_file_location('preparing_'+candidate,runner_path)
            runner=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
            if runner.config()['case_id']!=CASE:
                raise ValueError('Exact preparing case not bundled')
            survey={'map_name':'synthetic-reviewed-map','map_source':'synthetic:map',
                'lane_boundaries_source':'synthetic:lanes',
                'emergency_authorization_source':'synthetic:emergency-authority',
                'qualifying_flash_equipment_source':'synthetic:equipment-review',
                'officer_direction_review_source':'synthetic:officer-review',
                'preparing_to_move_source':'synthetic:independent-preparation-review',
                'visible_vehicle_movement_source':'synthetic:four-camera-motion-review',
                'ego_blueprint':'vehicle.ego','emergency_blueprint':'vehicle.emergency',
                'ego_spawn_xyz_m':[gap,0,0],'emergency_spawn_xyz_m':[0,3.5,0],
                'travel_heading_deg':0,
                'camera_world_transforms':{name:{'xyz_m':[0,0,3],
                    'rotation_deg':[0,0,0]} for name in runner.CAMERAS},
                'emergency_vehicle_authorized':True,
                'qualifying_flash_equipment_reviewed':True,
                'officer_directed_otherwise':False,
                'preparing_to_move_reviewed':True}
            runner.survey_check(survey)
            for key,value in (('preparing_to_move_reviewed',False),
                              ('preparing_to_move_source',None),
                              ('visible_vehicle_movement_source',None),
                              ('emergency_vehicle_authorized',False)):
                if not rejected(lambda k=key,v=value:runner.survey_check({**survey,k:v})):
                    raise ValueError('Unreviewed statutory source accepted: '+key)
            requests=[runner.reference_motion_request(i,'preparing_movement')
                      for i in (0,79,80,119,120,599)]
            if requests!=[0.0,0.0,0.5,0.5,4.0,4.0]:
                raise ValueError('Requested stopped/preparing/moving phases differ')
            if not rejected(lambda:runner.reference_motion_request(600,'preparing_movement')):
                raise ValueError('Out-of-window source motion accepted')
            construction=HERE/'draft-preparing-movement'/candidate/'construction.json'
            returned=HERE/'current-preparing-offline'/candidate/'offline.log'
            returned.parent.mkdir(parents=True,exist_ok=True)
            returned.write_text((out/'offline.log').read_text().rstrip()+'\n')
            results.append({'case_id':CASE,'candidate_id':candidate,
                'construction_sha256':sha(construction),
                'offline_log_sha256':sha(returned),'offline_passed':True,
                'survey_negative_checks':4,'request_phase_checks':7,
                'original_native_executed':False})
    proof={'format':'c404492-visible-preparation-draft-proof-v1',
           'manifest_sha256':manifest_sha,'results':results,
           'physical_acceptance_claimed':False,'legal_result':None}
    path=HERE/'current-preparing-draft-proof.json'
    path.write_text(json.dumps(proof,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'passed':True,'candidates':len(results),'proof_sha256':sha(path)},sort_keys=True))


if __name__=='__main__':main()
