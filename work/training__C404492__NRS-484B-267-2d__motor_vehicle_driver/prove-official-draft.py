"""Run pinned CPU offline and surveyed-authority checks for six official drafts."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args()
    scratch=args.scratch.resolve()
    if REPO/'.runtime-work' not in scratch.parents:
        raise ValueError('Scratch must be under .runtime-work')
    scratch.mkdir(parents=True,exist_ok=True)
    manifest=HERE/'draft-official-manifest.json'
    entries=json.loads(manifest.read_text())['cases']
    expected={'primary':-20,'fallback1':-25,'fallback2':-20}
    results=[]
    for entry in entries:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        for candidate,gap in expected.items():
            out=scratch/(suffix+'-'+candidate)
            command=[sys.executable,str(REPO/'runtime.py'),'offline',
                     '--manifest',str(manifest),'--case',entry['case_id'],
                     '--candidate',candidate,'--output',str(out),'--python',sys.executable]
            subprocess.run(command,check=True,capture_output=True,text=True,
                           env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
            bundle=out/'bundle'
            if not bundle.is_dir():
                bundle=out
            runner_path=bundle/'runner.py'
            if not runner_path.is_file():
                raise ValueError('Offline runner bundle missing')
            spec=importlib.util.spec_from_file_location(suffix+'_'+candidate,runner_path)
            runner=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
            survey={'map_name':'synthetic-reviewed-map','map_source':'synthetic:map',
                'lane_boundaries_source':'synthetic:lanes',
                'regulatory_agency_vehicle_source':'synthetic:agency-review',
                'qualifying_flash_equipment_source':'synthetic:equipment-review',
                'officer_direction_review_source':'synthetic:officer-review',
                'ego_blueprint':'vehicle.ego','emergency_blueprint':'vehicle.regulatory',
                'ego_spawn_xyz_m':[gap,0,0], 'emergency_spawn_xyz_m':[0,3.5,0],
                'travel_heading_deg':0,
                'camera_world_transforms':{name:{'xyz_m':[0,0,3],
                    'rotation_deg':[0,0,0]} for name in runner.CAMERAS},
                'official_regulatory_vehicle':True,
                'qualifying_flash_equipment_reviewed':True,
                'officer_directed_otherwise':False}
            runner.survey_check(survey)
            bad={**survey,'official_regulatory_vehicle':False}
            if not rejected(lambda:runner.survey_check(bad)):
                raise ValueError('Unreviewed regulatory authority accepted')
            bad={**survey,'regulatory_agency_vehicle_source':None}
            if not rejected(lambda:runner.survey_check(bad)):
                raise ValueError('Missing regulatory source accepted')
            bad={**survey,'qualifying_flash_equipment_reviewed':False}
            if not rejected(lambda:runner.survey_check(bad)):
                raise ValueError('Unreviewed flashing equipment accepted')
            construction=HERE/'draft-official'/suffix/candidate/'construction.json'
            results.append({'case_id':entry['case_id'],'candidate_id':candidate,
                'construction_sha256':sha(construction),'offline_passed':True,
                'survey_negative_checks':3,'simulation_started':False})
    result={'format':'c404492-official-cpu-draft-proof-v1',
            'manifest_sha256':sha(manifest),'results':results,
            'physical_acceptance_claimed':False,'legal_result':None}
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
