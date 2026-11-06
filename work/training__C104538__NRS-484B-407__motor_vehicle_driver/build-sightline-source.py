"""Retain three authored curve/crest sightline sources and damaged negatives."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from geometry import OBSERVER_DISTANCES_FT, obstruction_radius_for_limit, open_drive
from sightline import measure_source


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')


def build():
    root=HERE/'draft-sightline'
    root.mkdir(exist_ok=True)
    records=[]
    road_bytes=open_drive().encode()
    for suffix,requested in OBSERVER_DISTANCES_FT.items():
        folder=root/suffix
        folder.mkdir(exist_ok=True)
        road=folder/'road.xodr';road.write_bytes(road_bytes)
        obstruction=folder/'obstruction.json'
        write(obstruction,{'format':'c104538-authored-obstruction-v1',
                           'case_suffix':suffix,'road_xodr_sha256':sha(road),
                           'inner_radius_m':obstruction_radius_for_limit(requested),
                           'requested_reference_limit_ft':requested,
                           'native_actor_spawned':False,
                           'physical_opacity_measured':False})
        measured=measure_source(road,obstruction,suffix)
        if abs(measured['authored_reference_limit_ft']-requested)>1e-8:
            raise ValueError('Authored limit differs from requested geometry')
        write(folder/'measurement.json',measured)
        with tempfile.TemporaryDirectory() as temporary:
            missing=Path(temporary)/'obstruction.json'
            try:measure_source(road,missing,suffix)
            except ValueError as error:
                if str(error)!='Missing required source: obstruction.json':raise
            else:raise ValueError('Missing obstruction negative passed')
            damaged=Path(temporary)/'obstruction.json'
            changed=json.loads(obstruction.read_text());changed['road_xodr_sha256']='0'*64
            write(damaged,changed)
            try:measure_source(road,damaged,suffix)
            except ValueError as error:
                if str(error)!='Obstruction road source hash differs':raise
            else:raise ValueError('Wrong-road negative passed')
        records.append({'case_suffix':suffix,'requested_reference_limit_ft':requested,
                        'authored_reference_limit_ft':measured['authored_reference_limit_ft'],
                        'rays_at_500_ft':measured['rays_at_500_ft'],
                        'road_sha256':sha(road),'obstruction_sha256':sha(obstruction),
                        'measurement_sha256':sha(folder/'measurement.json'),
                        'missing_obstruction_rejected':True,'wrong_road_hash_rejected':True,
                        'native_loaded':False,'legal_verdict_claimed':False})
    summary={'format':'c104538-authored-sightline-source-summary-v1',
             'cases':records,'positive_count':3,'negative_count':6,
             'selected_delivery_cases':0,'physical_visibility_measured':False}
    write(root/'summary.json',summary)
    return summary


if __name__=='__main__':print(json.dumps(build(),indent=2))
