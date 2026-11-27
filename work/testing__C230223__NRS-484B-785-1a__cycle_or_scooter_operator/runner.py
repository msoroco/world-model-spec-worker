"""Exact source-gated original Native electric-scooter runner."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from package_spec import ACTOR,AID,CAMERA_NAMES,CELL,LAW
from scooter_785 import CASES,SOURCE_ROLES,need,validate_scene


def reviewed_site(path,case_id):
    path=Path(path).resolve()
    packet=json.loads(path.read_text())
    need(packet.get('reviewed_original_native_site') is True and
         packet.get('source_kind')=='original_native_map_geometry' and
         packet.get('assignment_id')==AID and packet.get('case_id')==case_id,
         'reviewed exact scooter site required')
    need(packet.get('duration_frames')==900 and packet.get('rate_hz')==20 and
         tuple(packet.get('cameras',()))==CAMERA_NAMES and packet.get('map_name'),
         'Native map and four-camera profile required')
    refs=packet.get('source_refs',[])
    need(isinstance(refs,list) and {'map',*SOURCE_ROLES}<={ref.get('role') for ref in refs},
         'independent official lane, device and ordinance sources required')
    for ref in refs:
        target=(path.parent/ref['path']).resolve()
        need(target.is_relative_to(path.parent) and target.is_file() and
             hashlib.sha256(target.read_bytes()).hexdigest()==ref.get('sha256'),
             'reviewed scooter source changed: '+ref.get('role','unknown'))
    need(packet.get('map_sha256')==next(ref['sha256'] for ref in refs if ref['role']=='map'),
         'Native map source differs')
    case=next((item for item in CASES if case_id==AID+'__'+item.name),None)
    need(case is not None,'unknown exact scooter case')
    scene=packet['scene']
    validate_scene(scene,case)
    for role in SOURCE_ROLES:
        need(scene[role+'_source_sha256']==next(ref['sha256'] for ref in refs if ref['role']==role),
             'reviewed scooter source binding differs: '+role)
    need(packet.get('scooter_blueprint_id','').startswith('vehicle.') and
         packet.get('spawn_z_m') is not None,
         'reviewed original Native scooter asset and spawn required')
    packet['reviewed_site_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    return packet,case


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--case')
    parser.add_argument('--site',type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    config=json.loads((Path(__file__).resolve().parent/'config.json').read_text())
    selected=config['selected_case_id']
    need((config.get('assignment_id'),config.get('law_id'),config.get('cell_id'),config.get('actor'))==
         (AID,LAW,CELL,ACTOR) and args.case in (None,selected),
         'exact scooter assignment differs')
    if args.check:
        print('exact scooter runner static check passed: '+selected)
        return
    site_path=args.site or os.environ.get('C230223_7851A_REVIEWED_SITE')
    need(site_path and args.host and args.port and args.output_dir is not None,
         'reviewed original scooter site, host, port and output required')
    site,case=reviewed_site(site_path,selected)
    from scooter_adapter import CarlaScooterAdapter
    from scooter_capture import capture
    adapter=CarlaScooterAdapter(args.host,args.port,site,case,config.get('engineering_profile',{}))
    capture(adapter,site,selected,args.output_dir)
    need(adapter.restoration_verified,'original Native scooter world restoration unverified')
    (args.output_dir/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'native','diagnostic_fixture':False,
        'physical_acceptance_claimed':False})+'\n')
    from worker_exchange.native_output import seal_capture
    seal_capture(args.output_dir,frames=900,
                 restoration={'restored':True,'settings_readback':'synchronous mode and delta verified'},
                 errors=[],encoder_exit_codes={name:0 for name in CAMERA_NAMES},
                 context={'reviewed_site_sha256':site['reviewed_site_sha256']})


if __name__=='__main__':
    main()
