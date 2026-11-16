"""Bind the exact marked-crosswalk primary to source-hashed inline files."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
CASE=HERE.name+'__marked_crosswalk_stop_before'
FILES=('runner.py','stop_sign_control.py','crosswalk_stop_measurements.py',
       'finalizer.py','site.json','config.json')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def emit(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def build():
 site=json.loads((HERE/'site.json').read_text())
 recording={'channels':[{'name':'halt_timing','unit':'structured record',
   'sampling_rate_hz':20,'method':'original complete-body/speed history joined to Native frames',
   'time_window':'entire capture','reference_frame':'original Native frame',
   'uncertainty':'proper sign and legal halt qualification unresolved'}],
   'context_inputs':[{'name':'stop_context','unit':'structured record',
      'method':'source-bound near-side crosswalk, Native sign and junction context'}],
   'limitations':['Synthetic site; physical and legal acceptance unclaimed']}
 config={'assignment_id':HERE.name,'selected_case_id':CASE,'law_id':'NRS-484A-450-2',
   'cell_id':'C331230','actor':'motor_vehicle_driver','rate_hz':20,'frames':900,
   'duration_s':45,'required_atoms':['ru.subject','ru.motor_vehicle','kin.position',
      'kin.speed','st.intersection','st.crosswalk'],
   'cameras':{'overview':[1920,1080],'approach':[1280,720],
      'reference_corner':[1280,720],'driver_reference':[1280,720]},
   'recording_description':recording,
   'site_packet':{'path':'site.json','sha256':sha(HERE/'site.json')},
   'physical_completion':{'criterion':'intersection_clearance',
      'motion_source':'stop_history.jsonl','body_key':'ego_body_vertices_xy_m',
      'intersection_polygon_xy_m':site['intersection_polygon_xy_m'],
      'exit_axis':0,'exit_sign':1,'minimum_progress_m':0.25,
      'engineering_tolerances_not_legal':True}}
 emit(HERE/'config.json',config)
 test='''import unittest\nfrom pathlib import Path\nfrom runner import load_config,CASE\nclass BundleTest(unittest.TestCase):\n def test_exact_crosswalk_case(self):\n  cfg,site=load_config(Path('.'))\n  self.assertEqual(cfg['selected_case_id'],CASE)\n  self.assertEqual(site['crosswalk_origin'],'marked')\n  self.assertFalse(site['physical_acceptance_claimed'])\n'''
 files=[{'path':name,'source':str((HERE/name).relative_to(REPO)),
         'content':(HERE/name).read_text()} for name in FILES]
 files.append({'path':'tests/test_bundle.py','content':test})
 construction={'case_id':CASE,'law_id':config['law_id'],'cell_id':config['cell_id'],
   'actor':config['actor'],'entrypoint':'runner.py','status':'synthetic_diagnostic_only',
   'recording_description':recording,
   'measurement_plan':{'procedure':'finalizer.py','source':'original stop-history, context, frame map and cameras'},
   'static_checks':['Exact case and site hash','marked near-side crosswalk precedes junction',
      'Native sign trigger and crosswalk are checked before capture'],
   'termination_rules':['900 synchronized frames','sensor/encoder cleanup and world restoration'],
   'mechanisms':['Native stop-sign trigger','complete-body stop/crosswalk measurement',
      'four original RGB cameras'], 'files':files}
 emit(HERE/'construction.json',construction)
 manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
   'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
   'cases':[{'case_id':CASE,'kind':'delivery','construction':'construction.json',
     'construction_sha256':sha(HERE/'construction.json'),
     'candidate_risk':{'status':'physical','reason':'Native stop position can overshoot the crosswalk'},
     'candidates':[],'measurement_procedure':{'entrypoint':'finalizer.py'},
     'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
       'port_env_var':'CARLA_PORT'}}],
   'status':'partial_first_case_cpu_bundle'}
 emit(HERE/'execution-manifest.json',manifest)
 return {'case_id':CASE,'construction_sha256':manifest['cases'][0]['construction_sha256'],
   'site_basis':site['review_basis']}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))
