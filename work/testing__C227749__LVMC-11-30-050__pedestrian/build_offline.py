"""Rebuild exact, source-hashed offline bundles for the five authored cases."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
RUNTIME='8c37e7719b3607424c88237d679368075e9278af4dddb569d2123f456e0fefa8'
CAMERAS=[{'name':name,'width':1920 if name=='overview' else 1280,
          'height':1080 if name=='overview' else 720,'fov_deg':75,
          'pose_strategy':'complete pedestrian crossing and both curbs'}
         for name in ('overview','approach','reference_corner','driver_reference')]
COMMON=['runner.py','crossing_geometry.py','native_controller.py','native_capture.py','walker_pipeline_capture.py','delivery_audit.py',
        'saved_measurement.py','comparison_audit.py','analysis.py']

def dump(p,obj): p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def build():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    entries=[]
    for case in plan['cases']:
        case_id=case['case_id'];directory=ROOT/case['construction'];directory=directory.parent
        config={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':'pedestrian',
                'selected_case_id':case_id,'supported_case_ids':[c['case_id'] for c in plan['cases']],
                'rate_hz':20,'duration_s':20,'required_atoms':[],'source_packets':[],
                'cameras':CAMERAS,
                'case':{'case_id':case_id,'physical_target':'original walker crossing route and sourced curb/crosswalk context',
                        'recording_description':{'channels':[{'name':name,'unit':unit,
                           'method':method,'time_window':'entire crossing','sampling_rate_hz':20,
                           'reference_frame':'source-bound world XY','uncertainty':'physical realization unconfirmed'}
                           for name,unit,method in [
                           ('walker_body_route','m','original Native walker body vertices and centers'),
                           ('curb_and_crosswalk_geometry','m','original map and site source packets'),
                           ('route_angle_and_length','degree and m','saved measurement from original body history'),
                           ('governing_context','source','municipal jurisdiction and original device context')]],
                           'context_inputs':[{'name':'roadway_and_jurisdiction','unit':'source','method':'reviewed source packet'}],
                           'limitations':['Authored scene is an engineering target; original map and site context pending.']}}}
        dump(directory/'config.json',config)
        files=[{'path':name,'source':str((ROOT/name).relative_to(ROOT.parents[1])),'content':(ROOT/name).read_text()} for name in COMMON]
        files += [{'path':'candidate-crossing.xodr','source':str((ROOT/'candidate-crossing.xodr').relative_to(ROOT.parents[1])),'content':(ROOT/'candidate-crossing.xodr').read_text()},
                  {'path':'scene.json','source':str((directory/'scene.json').relative_to(ROOT.parents[1])),'content':(directory/'scene.json').read_text()},
                  {'path':'config.json','source':str((directory/'config.json').relative_to(ROOT.parents[1])),'content':(directory/'config.json').read_text()},
                  {'path':'tests/test_offline.py','source':str((ROOT/'offline_test.py').relative_to(ROOT.parents[1])),'content':(ROOT/'offline_test.py').read_text()}]
        construction={'law_id':plan['law_id'],'cell_id':plan['cell_id'],'actor':'pedestrian',
                      'case_id':case_id,'entrypoint':'runner.py','files':files,
                      'recording_description':config['case']['recording_description'],
                      'measurement_plan':{'route_measurement':'source-bound original walker route against sourced finite curbs'},
                      'static_checks':['exact actor/case and 20 Hz four-camera plan','authored curb/route/crosswalk polygon geometry'],
                      'termination_rules':{'duration_s':20,'early_termination':'retain failed Native attempt'},
                      'mechanisms':['Native walker controller with readback','original body-history measurement; source map binding pending']}
        dest=directory/'construction.json';dump(dest,construction)
        entries.append({'case_id':case_id,'construction':str(dest.relative_to(ROOT)),
                        'construction_sha256':sha(dest),'candidates':[],
                        'measurement_contract':str((directory/'measurement-contract.json').relative_to(ROOT)),
                        'measurement_procedure':{'entrypoint':'analysis.py'},
                        'fixture_recipe':str((directory/'fixture-recipe.json').relative_to(ROOT.parents[1]))})
    manifest={'format':'c227749-draft-offline-manifest','assignment_id':plan['assignment_id'],
              'runtime_manifest_sha256':RUNTIME,'cases':entries,
              'limitations':'Offline authored geometry only; Native map, semantic and compatibility proofs pending.'}
    dump(ROOT/'draft-offline-manifest.json',manifest)
    return manifest

if __name__=='__main__': print(json.dumps(build(),indent=2))
