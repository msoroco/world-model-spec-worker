"""Update existing partition4 packages to continuation acceptance, preserving case IDs."""
import copy,hashlib,json,pathlib,subprocess,sys
R=pathlib.Path('.');HOME=R/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver';IDS=json.loads((R/'partitions/demo-test-04.json').read_text())['assignment_ids']
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
shared=['contracts.py','recording.py','worker_exchange/__init__.py','worker_exchange/common.py','worker_exchange/runtime_contract.py']
for aid in IDS:
 d=R/'work'/aid;cfg=read(d/'config.json');plan=read(d/'case-plan.json');proposal=read(d/'proposals/cases.json');mode=cfg['mode']
 cfg.pop('runtime_gaps',None);cfg['delivery_status']='blocked'
 requirements=[]
 def req(text,category,evidence,action,live):requirements.append(dict(requirement=text,category=category,evidence=evidence,next_action=action,requires_live_execution=live))
 if mode=='following':req('Measured physical gap tracking and hill-crest lane-change feasibility for the existing frozen capability settings; judgment sweep range cannot be accepted from synthetic software fixtures.','live_measurement',['runner.py: body-gap feedback controller and native lane/crest realization checks','proposals/cases.json: unresolved reasonable-and-prudent physical sweep','runtime/target-environment.json: CARLA unavailable to worker'],'Run each frozen physical target once with original recording on CARLA0.9.15; inspect measured gap/window, body containment, crest passage and lamp footage; finalize feasible range without treating it as a legal threshold.',True)
 if mode=='alley':req('Native collision-container blueprint and actual rendering of authored alley access-aisle lines and bounded corridor.','external_asset',['runner.py: alley_corridor queries native static.prop.* container inventory and validates extents; road_xml builds restricted strip with native white road marks','Repository contains authored OpenDRIVE but no installed blueprint inventory or rendered map asset survey'],'Provide compatible native collision-container blueprint in CARLA0.9.15; execute the frozen marked-aisle/corridor builder and retain surface/marking/camera proof from the original run.',True)
 if mode in ('posted','signal','inoperative'):
  feature={'posted':'narrow native road with a real 25mph sign, explicit governed portion/direction and physical sign/road-width proof','signal':'one-way approach into a two-way destination, actual governing signal heads, painted stop-line and precise intersection footprint boundary','inoperative':'blind intersection with installed uncovered native signals, native marked stop-line,230m incoming sight search routes, collision obstructions and two distinct earlier-stopped/occupying vehicle routes'}[mode]
  req('Verified native-scene asset/proof binding: '+feature+'.','external_asset',['native-binding-contract.json documents executable binding fields; runner.verify_binding checks map hash, proofs, native route/lane topology/device identity and required peer/obstruction mechanisms','Exact input witness requires physical features; repository does not contain a matching surveyed native map/device asset inventory'],'Provide --binding PATH with the verified original native map/proof files described by native-binding-contract.json. The existing runner constructs props/participants and checks actual realization; preserve frozen case assignments.',True)
 req('Actual original-run visibility, capture, vehicle dynamics and first-run target realization remain unmeasured.','live_measurement',['No simulator or CARLA runtime is available in this preparation worker','Offline success/failure fixtures validate software and actual CPU-encoded videos, not physical feasibility'],'Run on dedicated compatible CARLA resource with supplied runtime/python dependencies; retain all original evidence and use strict validate_output before downstream measured-results finalization.',True)
 cfg['runtime_requirements']=requirements
 desc=cfg['recording_description'];desc['limitations']=['Measured native projections preserve raw positions, speeds, body geometry, device states and event histories; no legal verdict, inferred public authority or judgment cutoff.','Engineering cessation <=0.05m/s and 0.5mph tracking tolerance are measurement conventions, never legal tolerances.']
 for channel in desc['channels']:
  channel['method']='native velocity norm' if channel['name']=='kin.speed' else 'same-original-frame '+channel['name']+' measurement projection; source native actor/device APIs and retained authored geometry'
  channel['uncertainty']='50ms frame/event bracket plus native geometry and sensor uncertainty; no inferred legal precision'
 # Keep every frozen case identity and scalar assignment; update recording implementation consistently.
 for c in proposal['cases']:c['recording_description']=copy.deepcopy(desc)
 for s in proposal['sweep_specs']:
  s['recording_description']=copy.deepcopy(desc);s['missing_inputs']=[r['requirement'] for r in requirements if r['category']=='live_measurement']
 cfg['cases']=copy.deepcopy(proposal['cases']);plan['cases']=copy.deepcopy(proposal['cases']);plan['runtime_uncertainties']=[r['requirement'] for r in requirements]
 # Remove superseded authored statement that called headway a legal bound; keep original summary source intact.
 if mode=='following':
  plan['summary_text_conflicts']=[{'source':'assignment.summary.required_observations[drv.time_gap] and timing_requirements','conflict':'Summary calls headway an operationalization and assumes a bound; exact law supplies only reasonable and prudent. No legal headway bound is adopted.','resolution':'retain raw gap/speed/time histories and unresolved phrase'}]
 if mode=='alley':plan['summary_text_conflicts']=[{'source':'assignment.summary.activation_conditions','conflict':'Summary adds highway to exact clause In any event, while witness preserves territorial applicability and definitions.','resolution':'retain territorial applicability and statutory scope unresolved; no extra legal activation inferred'}]
 write(d/'config.json',cfg);write(d/'case-plan.json',plan);write(d/'proposals/cases.json',proposal)
 (d/'runner.py').write_text((HOME/'runtime_v3.py').read_text());(d/'runner.py').chmod(0o755);(d/'projections.py').write_text((HOME/'projections_template.py').read_text())
 for rel in shared:
  target=d/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_text((R/'work/_shared'/rel).read_text())
 schema={'description':'External verified native-scene asset/proof binding. It is not a source of observations; the runner verifies map/assets/lanes and captures actual behavior. Native proofs must exist with exact SHA256.','status':'verified','required_fields':['map_sha256','physical_feature_proofs:[{path,sha256,feature}]','route:[[x,y,z],...] with<=4m gaps','driving_polygons:[[[x,y],...],...]','incoming_topology:all native lane links and intersection IDs','intersection_polygon:[[x,y],...]','stop_line:{reference_position_m:[x,y,z],vertices_m,source} physically rendered, not an overlay','crosswalks:native Map.get_crosswalks vertices','device_governance:explicit native actor/lane/region IDs and physical proof','signal_actor_ids:[native integer IDs]','signal_proof:{installed,uncovered,proof_references}','authored_lane_width_m for narrow-road sign probe','speed_sign:{actor_id,blueprint,value_mph:25,position_m},governed_polygon for posted speed','obstruction_props:[{blueprint,position_m,yaw_deg}] for blind intersection','peer_routes:[{role:earlier_stopped|intersection_occupying,route:[[x,y,z],...],speed_mps,stop_position_m,release_time_s}] for blind intersection','incoming_lane_extent_m:[at least230m per incoming route] for sight capture'],'forbidden':['Map overlays as physical features','Changing frozen comparison variables to fit available map','Empty or guessed physical proof records','Using a public-authority assumption to substitute for an absent physical sign']}
 write(d/'native-binding-contract.json',schema)
 # Regression and strict actual-video contract fixtures are executed in every materialized case bundle.
 (d/'tests/test_retained_output.py').write_text((R/'work/_shared/tests/test_contracts.py').read_text())
 (d/'tests/test_package.py').write_text('''import importlib.util,pathlib,unittest,json,math,sys
P=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(P))
spec=importlib.util.spec_from_file_location('runtime_case',P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
from projections import Projection,inside,intersects,hull,validate_visibility
class TestPackage(unittest.TestCase):
 def test_offline(self):m.offline_check()
 def test_brake(self):self.assertGreater(m.control(0,0,0,15,[(x,0) for x in range(100)],3)['brake'],0)
 def test_heading_wrap(self):self.assertEqual(m.heading_error(359,1),2)
 def test_gap_uses_footprints(self):self.assertEqual(m.physical_gap([[0,0],[4,0]],[[20,0],[24,0]],[1,0]),16)
 def test_observed_window(self):self.assertEqual(m.summarize([dict(time_s=1,value=100),dict(time_s=16,value=3),dict(time_s=20,value=5)],15,24),(4,[16,20]))
 def test_empty_window_rejected(self):
  with self.assertRaises(ValueError):m.summarize([],15,24)
 def test_no_requested_measurements(self):
  for c in json.loads((P/'config.json').read_text())['cases']:
   for v in c['variable_assignments'].values():
    if v['kind']=='subject_behavior':self.assertIsNone(v['value'])
 def test_runtime_has_conditional_success(self):
  source=(P/'runner.py').read_text();self.assertIn('return 0 if success else 2',source);self.assertNotIn('return 2 # Partial',source)
 def test_box_hull_ignores_native_corner_order(self):self.assertEqual(len(hull([[0,0],[1,1],[1,0],[0,1],[0,0]])),4)
 def test_edge_crossing_overlap(self):self.assertTrue(intersects([[-2,-.1],[2,-.1],[2,.1],[-2,.1]],[[-.1,-2],[.1,-2],[.1,2],[-.1,2]]))
 def event(self,speed=3,time=.05):
  a=dict(actor_id=1,blueprint='vehicle.fixture',heading_deg=0,body_vertices_m=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]],position_m=[0,0,0],velocity_mps=[speed,0,0],speed_mps=speed,accel_longitudinal_mps2=-1)
  b=dict(a,actor_id=2,body_vertices_m=[[10,0,0],[11,0,0],[11,1,0],[10,1,0]],position_m=[10,0,0])
  return dict(frame=1,time_s=time,speed_mps=speed),dict(original_observations=dict(participants=[a,b],devices=[],relations=[]),world=dict(road_projection={'road_id':1,'lane_id':-1},weather={'wetness':0,'precipitation_deposits':0}))
 def test_measured_projection_gap(self):
  p=Projection(1,['rel.surface_gap','kin.speed'],dict(leader_id=2,driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event();self.assertEqual(p(r,e)['rel.surface_gap'],9)
 def test_missing_required_leader_fails(self):
  p=Projection(1,['rel.surface_gap'],dict(leader_id=99,driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event()
  with self.assertRaises(ValueError):p(r,e)
 def test_stationary_initialization_is_not_stop_event(self):
  p=Projection(1,['kin.speed'],dict(driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event(0);p(r,e);self.assertEqual(p.stop_events,{})
 def test_history_timestamp_mismatch(self):
  trace=[{'time_s':0}];people=[{'time_s':1,'participants':[]}];body=[{'time_s':0,'vertices':[[0,0]]}]
  with self.assertRaises(ValueError):m.validate_histories(trace,people,body,[])
 def test_unmeasured_participant_rejected(self):
  with self.assertRaises(ValueError):m.validate_histories([{'time_s':0}],[{'time_s':0,'participants':[{'actor_id':1}]}],[{'time_s':0,'vertices':[[0,0]]}],[1])
 def test_missing_sight_approach_rejected(self):
  with self.assertRaises(ValueError):validate_visibility({'visibility_criterion':'any_of_nine_body_samples','required_lane_ids':[-1,1],'approaches':[]})
 def test_route_limited_sight_rejected(self):
  with self.assertRaises(ValueError):validate_visibility({'visibility_criterion':'any_of_nine_body_samples','required_lane_ids':[-1],'approaches':[{'lane_id':-1,'any_body_sight_horizon':{'bound':'route_limit','unknown':True}}]})
 def test_actual_cessation_history(self):
  p=Projection(1,['kin.speed'],dict(driving_polygons=[[[-10,-10],[20,-10],[20,20],[-10,20]]],surface={'authored':'dry'}));r,e=self.event(3);p(r,e);r,e=self.event(0,.1);p(r,e);self.assertEqual(p.stop_events[1]['previous_time_s'],.05)
''')
 # Refresh all input and shared source hashes; the repository update changed contracts, not case targets.
 sources=[R/'inputs'/aid/'assignment.json',R/'runtime/stage-contracts.json',R/'runtime/target-environment.json',R/'runtime/python/pipeline_capture.py',R/'runtime/python/original_observations.py',R/'updates/003.json']+[R/'work/_shared'/p for p in shared]
 plan['sources']=[{'path':str(p),'sha256':sha(p)} for p in sources];write(d/'case-plan.json',plan)
 def construction(case,anchor=False):
  c=copy.deepcopy(cfg);c['default_case_id']=case['case_id'];casefile=d/'case-configs'/(case['case_id']+'.json');write(casefile,c)
  files=[]
  for rel in ['runner.py','projections.py','road-template.xodr','proposals/cases.json','native-binding-contract.json']:
   files.append({'path':rel,'content':(d/rel).read_text()})
  files.append({'path':'config.json','source':str(d/'config.json' if anchor else casefile),'content':(d/'config.json' if anchor else casefile).read_text()})
  for rel in shared:files.append({'path':rel,'source':str(R/'work/_shared'/rel),'content':(R/'work/_shared'/rel).read_text()})
  return {'cell_id':cfg['cell_id'],'actor':cfg['actor'],'case_id':case['case_id'],'status':'draft','files':files,'entrypoint':'runner.py','mechanisms':['native physical path/speed/gap control','authored OpenDRIVE restricted marked access-aisle and collision-prop corridor, or verified native-device asset binding','native crest/two-lane geometry and body containment','distinct peer halt/occupancy controllers','original20Hz PipelineCapture and4 encoded VP9/WebM original RGB streams'],'measurement_plan':{'frozen_speed_window_s':cfg['measurement_window_s'],'speed_mps_tracking_engineering_tolerance':.5*.44704,'following_gap_window_s':[5,14],'following_gap_tracking_engineering_tolerance_m':2,'cessation_engineering_convention_mps':.05,'mandatory_channels':'projections.py measures each channel from actual original actor/device/geometry data; no packets substituted for scalars','target_checks':'measured_target and strict validate_output; failed matched/cause evidence cannot succeed','physical_feature_proof':'native-binding-contract.json plus setup-evidence.json; authority remains synthetic context'},'recording_description':desc,'static_checks':['--check configuration/case/speed-policy/geometry checks','successful and failing actual-encoded output fixtures','measured mandatory-channel projection/cessation/footprint/history/cleanup regression tests'],'termination_rules':{'duration_s':cfg['duration_s'],'events':['signal','collision','roadway_departure','loss_of_control','frame/capture/target mismatch'],'cleanup':'independent resources close encoders/sensors/owned actors, signals, weather and prior world settings; never stop the simulator server'}}
 write(d/'construction.json',construction(proposal['cases'][1],True))
 for c in proposal['cases'][2:]:write(d/'constructions'/(c['case_id']+'.json'),construction(c))
 write(d/'update-acknowledgements.json',{'assignment_id':aid,'applied_update':3,'notices':[{'version':2,'action':'continue','status':'applied'},{'version':3,'action':'continue','status':'applied','instructions':'Preserved existing cases; implemented mandatory projections, encoded capture, physical feature builders, full result checks and independent cleanup. External asset/live requirements structured.'}],'paused':False})
 result=read(d/'result.json');result.update(status='blocked',applied_update=3,reason='Executable implementation complete; external native assets/proofs or actual live physical measurements required as listed.',requirements=requirements,externally_blocked_requirements=requirements)
 tests=[]
 for name,cmd in [('check',['python3.11',str(d/'runner.py'),'--check']),('unittest',['python3.11','-m','unittest','discover','-s',str(d/'tests')])]:
  p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);log=d/'logs'/(name+'.log');log.write_text(p.stdout);tests.append({'command':' '.join(cmd),'exit_code':p.returncode,'log':str(log.relative_to(d)),'sha256':sha(log)})
 result['tests']=tests;result['six_steps']={'inputs':'exact law/cell/actor/witness/summary/evidence read; text/summary conflicts explicit','cases':'preserved statutory triples and physical action comparisons; judgment phrase unresolved','implementation':'physical feature/controller builders, native proof bindings, measured projections and original VP9 capture','checks':'strict measured target/video/channel/history/footprint/sight and independent cleanup acceptance','offline_tests':'positive and failing actual encoded-output fixtures plus assignment regressions','handoff':'only structured external asset/live requirements remain'};write(d/'result.json',result)
 (d/'HANDOFF.md').write_text('''# Continuation delivery: externally blocked

Executable implementation now includes physical scene/participant/controllers, per-channel measured native projections, four VP9/WebM streams, original PipelineCapture, full matching-frame trace/channel histories, body containment and participant history evidence, measured target checks and strict result acceptance. The runner can return success only after actual setup, maneuver, target, video/frame/channel/history and cleanup checks pass. No simulator was run. CPU fixtures include successful and failing real encoded-video evidence.

Baseline remains unselected. Exact case IDs and scalar assignments were preserved. Statutory speed probes use +/-5mph and an at command0.5mph inside the compliant side. Judgment semantics remain unresolved; engineering cessation0.05m/s, gap2m and speed0.5mph tracking criteria are not legal standards.

Offline: `python3.11 runner.py --check` and `python3.11 -m unittest discover -s tests`. Materialize every construction via `python3.11 work/_shared/materialize.py --assignment ASSIGNMENT_ID` from the repository. Live: `python3 runner.py --output-dir PATH --host HOST --port PORT --case-id CASE_ID`, plus `--binding PATH` for native-device-dependent packages. The runtime needs compatible CARLA0.9.15, supplied runtime/python dependencies, native assets, ffmpeg/libvpx-vp9 and ffprobe. No CARLA server lifecycle is owned.

Structured external requirements:

'''+ '\n'.join('- '+r['category']+': '+r['requirement']+' Next: '+r['next_action'] for r in requirements)+'''

Measured-results finalization: retain the complete original trace, recorder, road.xodr, raw native graphs/evidence, all mandatory projected streams, setup evidence, participant/footprint histories, four full RGB WebM files and zero-based original frame map. Strict validate_output recomputes summaries from saved sample windows, decodes video frame counts/rates, validates mandatory values/times, measured targets/cause references and full body/history coverage. Review actual feature visibility in original RGB; a controller request is never evidence of realization. No legal verdict or subjective cutoff is produced. Freeze targets across evidence-backed repairs and retain failed attempts; no unchanged retries or retrospective range changes.

Additional canonical case proposals (same implementation, case-specific config with exact source equality):

'''+ '\n'.join('- constructions/'+c['case_id']+'.json' for c in proposal['cases'][2:])+'''

Update003 continuation processed, no pause active. Result logs and source hashes are exact. Blocked means external asset or live physical evidence, not unfinished implementation.
''')
 print(aid,[x['exit_code'] for x in tests])
