"""Build the no-crosswalk marked-stop-line exact CPU construction."""
import hashlib,json
from pathlib import Path
F=Path(__file__).resolve().parent;R=F.parents[1]
D=F/'cases/no_crosswalk_marked_stop_line';D.mkdir(parents=True,exist_ok=True)
CASE=F.name+'__no_crosswalk_marked_stop_line'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def emit(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def change(s,old,new):
 assert s.count(old)==1,(old[:100],s.count(old))
 return s.replace(old,new)
def build():
 site=json.loads((F/'site.json').read_text())
 site.update(format='worker-c331230-no-crosswalk-stop-line-site',near_side_crosswalk_exists=False,
             crosswalk_absence_source='synthetic map and sidewalk inventory; Native review pending',
             stop_line_exists=True,stop_line_segment_xy_m=[[6.0,-3.0],[6.0,3.0]],
             stop_line_marking_source='synthetic authored marking; original pixel and Native review pending')
 site.pop('crosswalk_polygon_xy_m');site.pop('crosswalk_origin');emit(D/'site.json',site)
 runner=(F/'runner.py').read_text()
 runner=change(runner,"CASE='testing__C331230__NRS-484A-450-2__motor_vehicle_driver__marked_crosswalk_stop_before'",f"CASE='{CASE}'")
 runner=change(runner,"site.get('near_side_crosswalk_exists') is not True or\n     site.get('crosswalk_origin')!='marked' or\n     site.get('stop_line_exists') is not False", "site.get('near_side_crosswalk_exists') is not False or\n     not site.get('crosswalk_absence_source') or\n     site.get('stop_line_exists') is not True or\n     not site.get('stop_line_marking_source')")
 runner=change(runner,"cross=site['crosswalk_polygon_xy_m'];junction=site['intersection_polygon_xy_m']\n if (len(cross)<4 or len(junction)<4 or\n     max(x for x,y in cross)>=min(x for x,y in junction) or\n     site['ego_spawn_pose'][0]>=min(x for x,y in cross)):\n  raise ValueError('Crosswalk must precede junction and spawn')", "line=site['stop_line_segment_xy_m'];junction=site['intersection_polygon_xy_m']\n if (len(line)!=2 or len(junction)<4 or\n     max(x for x,y in line)>=min(x for x,y in junction) or\n     site['ego_spawn_pose'][0]>=min(x for x,y in line) or\n     not (min(y for x,y in line)<=site['ego_spawn_pose'][1]<=max(y for x,y in line))):\n  raise ValueError('Marked stop line must precede junction and spawn')")
 start=runner.index('def _source_context(');end=runner.index('def _camera_process(',start)
 runner=runner[:start]+'''def _source_context(site,sign):
 return {'native_map_id':site['native_map_name'],'intersection_id':site['intersection_id'],
  'approach_road_id':site['approach_road_id'],'approach_lane_id':site['approach_lane_id'],
  'native_stop_sign_id':sign.id,'sign_governance_source':'Native trigger plus unreviewed site packet',
  'junction_source':'unreviewed synthetic site geometry',
  'near_side_crosswalk_exists':False,'crosswalk_absence_source':site['crosswalk_absence_source'],
  'stop_line_exists':True,'stop_line_marking_source':site['stop_line_marking_source'],
  'stop_line_segment_xy_m':site['stop_line_segment_xy_m'],
  'intersection_polygon_xy_m':site['intersection_polygon_xy_m'],
  'approach_forward_xy':[1,0],
  'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}

'''+runner[end:]
 runner=change(runner,"crosswalks=world_map.get_crosswalks()\n x0=min(p[0] for p in site['crosswalk_polygon_xy_m']);x1=max(p[0] for p in site['crosswalk_polygon_xy_m'])\n y0=min(p[1] for p in site['crosswalk_polygon_xy_m']);y1=max(p[1] for p in site['crosswalk_polygon_xy_m'])\n if not any(x0<=p.x<=x1 and y0<=p.y<=y1 for p in crosswalks):\n  raise ValueError('Native near-side crosswalk differs from authored polygon')", "crosswalks=world_map.get_crosswalks()\n x0=min(p[0] for p in site['stop_line_segment_xy_m']);x1=min(p[0] for p in site['intersection_polygon_xy_m'])\n y0=min(p[1] for p in site['stop_line_segment_xy_m']);y1=max(p[1] for p in site['stop_line_segment_xy_m'])\n if any(x0-2<=p.x<=x1 and y0-2<=p.y<=y1+2 for p in crosswalks):\n  raise ValueError('Native near-side crosswalk exists; stop-line branch inapplicable')")
 runner=change(runner,"if any(x0-2<=p.x<=x1 and y0-2<=p.y<=y1+2 for p in crosswalks):\n  raise ValueError('Native near-side crosswalk exists; stop-line branch inapplicable')","if not native_crosswalk_absent(site,crosswalks):\n  raise ValueError('Native near-side crosswalk exists; stop-line branch inapplicable')")
 marker='def capture(root,host,port):'
 assert runner.count(marker)==1
 runner=runner.replace(marker,'''def native_crosswalk_absent(site,crosswalks):
 x0=min(p[0] for p in site['stop_line_segment_xy_m']);x1=min(p[0] for p in site['intersection_polygon_xy_m'])
 y0=min(p[1] for p in site['stop_line_segment_xy_m']);y1=max(p[1] for p in site['stop_line_segment_xy_m'])
 return not any(x0-2<=p.x<=x1 and y0-2<=p.y<=y1+2 for p in crosswalks)

'''+marker)
 runner=change(runner,'C331230 exact marked-crosswalk CPU check passed','C331230 exact no-crosswalk stop-line CPU check passed')
 runner=change(runner,'from crosswalk_stop_measurements import analyze','from stop_reference_measurements import analyze')
 runner=change(runner,"ordered=observation['full_halt_before_crosswalk_and_junction_observed']", "ordered=observation['halt_before_reference_and_junction_observed']")
 runner=change(runner,"'measured_values':{'halt_before_crosswalk_observed':ordered}","'measured_values':{'halt_before_stop_line_observed':ordered}")
 runner=change(runner,"'target':'complete_halt_before_nearside_crosswalk'","'target':'complete_halt_before_marked_stop_line'")
 runner=change(runner,"'method':'original complete-body speed and crosswalk geometry'","'method':'original complete-body speed and marked-line geometry'")
 (D/'runner.py').write_text(runner)
 (D/'finalizer.py').write_text((F/'stop_reference_finalizer.py').read_text())
 cfg=json.loads((F/'config.json').read_text());cfg['selected_case_id']=CASE;cfg['required_atoms']=[a for a in cfg['required_atoms'] if a!='st.crosswalk'];cfg['site_packet']['sha256']=sha(D/'site.json')
 cfg['recording_description']['context_inputs'][0]['method']='source-bound Native sign, no-crosswalk inventory and marked stop line'
 cfg['recording_description']['limitations']=['Synthetic no-crosswalk/stop-line site; Native and legal review pending']
 cfg['physical_completion']['intersection_polygon_xy_m']=site['intersection_polygon_xy_m']
 emit(D/'config.json',cfg)
 test='''import unittest\nfrom pathlib import Path\nfrom runner import load_config,CASE\nclass BundleTest(unittest.TestCase):\n def test_exact_stop_line_case(self):\n  cfg,site=load_config(Path('.'))\n  self.assertEqual(cfg['selected_case_id'],CASE)\n  self.assertFalse(site['near_side_crosswalk_exists'])\n  self.assertTrue(site['stop_line_exists'])\n  self.assertLess(max(p[0] for p in site['stop_line_segment_xy_m']),min(p[0] for p in site['intersection_polygon_xy_m']))\n  self.assertFalse(site['physical_acceptance_claimed'])\n def test_native_crosswalk_absence_guard(self):\n  from types import SimpleNamespace as NS\n  from runner import native_crosswalk_absent\n  _,site=load_config(Path('.'))\n  self.assertTrue(native_crosswalk_absent(site,[]))\n  self.assertFalse(native_crosswalk_absent(site,[NS(x=7,y=0)]))\n  self.assertTrue(native_crosswalk_absent(site,[NS(x=100,y=0)]))\n'''
 files=[]
 for name,path in [('runner.py',D/'runner.py'),('finalizer.py',D/'finalizer.py'),('stop_sign_control.py',F/'stop_sign_control.py'),('stop_reference_measurements.py',F/'stop_reference_measurements.py'),('crosswalk_stop_measurements.py',F/'crosswalk_stop_measurements.py'),('site.json',D/'site.json'),('config.json',D/'config.json')]:
  files.append({'path':name,'source':str(path.relative_to(R)),'content':path.read_text()})
 files.append({'path':'tests/test_bundle.py','content':test})
 construction={'case_id':CASE,'law_id':'NRS-484A-450-2','cell_id':'C331230','actor':'motor_vehicle_driver','entrypoint':'runner.py','status':'synthetic_diagnostic_only',
  'recording_description':cfg['recording_description'],
  'measurement_plan':{'procedure':'finalizer.py','source':'original stop, sign, line, frame map and camera sources'},
  'static_checks':['Exact no-crosswalk/line case and site hash','marked line precedes junction',
    'Native sign trigger and crosswalk absence checked before capture'],
  'termination_rules':['900 synchronized frames','sensor/encoder cleanup and world restoration'],
  'mechanisms':['Native governing stop sign','complete-body stop-line measurement','four original RGB cameras'],
  'files':files}
 emit(D/'construction.json',construction)
 manifest_path=F/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
 entry={'case_id':CASE,'kind':'delivery','construction':'cases/no_crosswalk_marked_stop_line/construction.json',
  'construction_sha256':sha(D/'construction.json'),
  'candidate_risk':{'status':'physical','reason':'Native stop may overshoot marking or the selected map may contain a crosswalk'},
  'candidates':[],'measurement_procedure':{'entrypoint':'finalizer.py'},
  'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}}
 prior=next((x for x in manifest['cases'] if x['case_id']==CASE),None)
 if prior:
  for key in ('fixture_recipe','measurement_contract','acquisition'):
   if key in prior:entry[key]=prior[key]
 manifest['cases']=[x for x in manifest['cases'] if x['case_id']!=CASE]
 manifest['cases'].append(entry);manifest['status']='partial_two_case_cpu_bundle';emit(manifest_path,manifest)
 return {'case_id':CASE,'construction_sha256':entry['construction_sha256']}
if __name__=='__main__':print(json.dumps(build()))
