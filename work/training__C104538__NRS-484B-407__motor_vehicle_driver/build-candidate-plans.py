"""Retain 12 unselected plans bound to source measurement hashes."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from engineering import CANDIDATES,check,plan
from geometry import OBSERVER_DISTANCES_FT


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def build():
    check()
    rows=[]
    for suffix in OBSERVER_DISTANCES_FT:
        source=HERE/'draft-sightline'/suffix
        measured=json.loads((source/'measurement.json').read_text())
        for candidate in CANDIDATES:
            record=plan(suffix,candidate)
            record['source_files']={name:sha(source/name)
                                    for name in ('road.xodr','obstruction.json','measurement.json')}
            dest=HERE/'draft-candidates'/suffix/candidate
            dest.mkdir(parents=True,exist_ok=True)
            write(dest/'plan.json',record)
            rows.append({'case_suffix':suffix,'candidate_id':candidate,
                         'plan_sha256':sha(dest/'plan.json'),
                         'construction_sha256':record['construction_sha256'],
                         'requested_reference_limit_ft':measured['requested_reference_limit_ft'],
                         'physical_trigger_measured':False,'selected':False})
    result={'format':'c104538-unselected-candidate-plan-manifest-v1',
            'rows':rows,'count':len(rows),'exact_offline_pass_count':0,
            'positive_compatibility_pass_count':0,'selected_delivery_cases':0}
    write(HERE/'draft-candidate-manifest.json',result)
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
