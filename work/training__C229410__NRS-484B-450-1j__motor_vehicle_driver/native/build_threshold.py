"""Package only the added engineering equality targets; preserve older bundles."""
import hashlib
import json
from pathlib import Path
from branch_variants import BRANCHES
from source_channels import SOURCE_NAMES

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
ASSIGNMENT=ROOT.name
CAMERAS=['overview','approach','reference_corner','driver_reference']
SUFFIXES=('same_at','opposite_at')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    manifest_path=ROOT/'expanded-native-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    existing={item['case_id'] for item in manifest['cases']}
    built=[]
    for suffix in SUFFIXES:
        branch=BRANCHES[suffix]
        case_id=ASSIGNMENT+'__'+suffix
        description={'channels':[{'name':'parking_geometry','unit':'mixed',
            'sampling_rate_hz':20,'method':'original Native full-body corners and speed readback',
            'time_window':'600 frames','reference_frame':'sourced highway and fire-station entrance',
            'uncertainty':'50 ms interval; statutory distance reference unresolved'}],
            'context_inputs':[{'name':name,'unit':'structured',
                'method':'original hash-bound authority and Native actor source; retain unverified state'}
                for name in SOURCE_NAMES],
            'limitations':['Engineering equality target is not a legal reference-point determination',
                'Actual station, entrance, direction and pixels require independent review']}
        config={'case_id':case_id,'case_suffix':suffix,'cell_id':'C229410',
            'law_id':'NRS-484B-450-1j','actor':'motor_vehicle_driver',
            'duration_s':30,'rate_hz':20,'cameras':CAMERAS,
            'initial_activity':branch.activity,'exception_context':branch.exception,
            'selected_case_id':case_id,'supported_case_ids':[case_id],
            'candidate_id':'primary','required_atoms':[],'source_packets':[],
            'case':{'case_id':case_id},'recording_description':description,
            'target':'source-reviewed parked at '+branch.side+' side engineering equality target'}
        files=[{'path':'config.json','content':json.dumps(config,indent=2)+'\n'}]
        module_names = (('layout.py','measure_entrance.py','source_context.py',
                         'source_channels.py','finalize.py') if suffix == 'same_at' else
                        ('branch_variants.py','expanded_layout.py','expanded_controller.py',
                         'expanded_measurement.py','measure_entrance.py','source_context.py',
                         'source_channels.py','expanded_finalize.py'))
        for name in module_names:
            files.append({'path':name,'content':(HERE/name).read_text()})
        if suffix == 'same_at':
            files += [{'path':'runner.py','content':(HERE/'threshold_same_runner.py').read_text()},
                      {'path':'tests/test_native.py','content':(HERE/'tests/test_native.py').read_text()}]
        else:
            files += [{'path':'runner.py','content':(HERE/'expanded_runner.py').read_text()},
                      {'path':'finalize.py','content':(HERE/'expanded_finalize.py').read_text()},
                      {'path':'tests/test_expanded_bundle.py','content':(HERE/'tests/test_expanded_bundle.py').read_text()}]
        for name in ('assignment.json','witnesses.json'):
            source=Path('inputs')/ASSIGNMENT/name
            files.append({'path':name,'content':source.read_text()})
        proposal={'case_id':case_id,'cell_id':'C229410','law_id':'NRS-484B-450-1j',
            'actor':'motor_vehicle_driver','entrypoint':'runner.py','files':files,
            'recording_description':description,'status':'partial_branch_construction',
            'physical_acceptance_claimed':False}
        target=HERE/'bundles'/suffix/'construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(proposal,indent=2)+'\n')
        entry={'case_id':case_id,'kind':'delivery','construction':str(target.relative_to(ROOT)),
            'construction_sha256':sha(target),'candidates':[],'delivery_readiness':'incomplete'}
        if case_id in existing:
            manifest['cases']=[item for item in manifest['cases'] if item['case_id']!=case_id]
        manifest['cases'].append(entry)
        built.append(entry)
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    return {'added_cases':[x['case_id'] for x in built],'manifest':str(manifest_path)}

if __name__=='__main__':
    print(json.dumps(build()))
