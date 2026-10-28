import pathlib,json,copy,hashlib,subprocess,shutil
R=pathlib.Path.cwd();A=R/'work/testing__C109705__NRS-484B-400-2a__motor_vehicle_driver';ids=json.loads((R/'partitions/demo-test-01.json').read_text())['assignment_ids']
def dump(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
shared=['contracts.py','recording.py','worker_exchange/__init__.py','worker_exchange/common.py','worker_exchange/runtime_contract.py']
extra_tests='''
import importlib.util,math
spec=importlib.util.spec_from_file_location('owned_runner',pathlib.Path(__file__).resolve().parents[1]/'runner.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class Geometry(unittest.TestCase):
 def test_all_configured_routes(self):runner.check()
 def test_curved_path_controller(self):
  c=runner.command((0,0),0,4,[[i,i*.2] for i in range(40)],5);self.assertGreater(c['steer'],0);self.assertGreater(c['throttle'],0)
 def test_all_routes_full_engineering_footprint(self):
  c=json.loads((pathlib.Path(__file__).resolve().parents[1]/'config.json').read_text())
  for case in json.loads((pathlib.Path(__file__).resolve().parents[1]/'proposals/cases.json').read_text())['cases']:
   path=runner.route(c,case)
   for a,b in zip(path,path[1:]):
    theta=math.atan2(b[1]-a[1],b[0]-a[0]);vertices=[[a[0]+dx*math.cos(theta)-dy*math.sin(theta),a[1]+dx*math.sin(theta)+dy*math.cos(theta)] for dx,dy in [(-2.4,-1.1),(-2.4,1.1),(2.4,-1.1),(2.4,1.1)]]
    self.assertTrue(runner.footprint_inside(vertices),vertices)
 def test_actual_speed_not_setpoint(self):
  class V:x=3;y=4;z=0
  self.assertEqual(runner.speed(V()),5)
 def test_brake_overspeed(self):self.assertGreater(runner.command((0,0),0,10,[[i,0] for i in range(40)],3)['brake'],0)
 def test_authored_cross_surface(self):
  self.assertTrue(runner.footprint_inside([[-30,1],[1,4],[3,20]]));self.assertFalse(runner.footprint_inside([[30,30]]))
 def test_raw_observation_values(self):
  s=dict(actor_id=1,time_s=1,position_m=[1,2,0],heading_deg=0,speed_mps=4,body_vertices_m=[[0,1,0],[2,1,0]],native_lane={'road_id':1,'lane_id':-1},lamp_bits=0,blueprint='vehicle.tesla.model3')
  names=['kin.speed','kin.position','drv.turning','drv.yields_to','rel.surface_gap','st.centre_line','sig.turn_indicator','ru.trailer_or_combination'];o=runner.atom_measurements(names,s,[s],{},[])
  self.assertEqual(set(o),set(names));self.assertEqual(o['kin.speed'],4);self.assertIn('no qualitative predicate',o['drv.yields_to']['method']);self.assertTrue(all(v is not None for v in o.values()))
'''
for aid in ids:
 w=R/'work'/aid;d=json.loads((R/'inputs'/aid/'assignment.json').read_text());law=d['law_id'];old=json.loads((w/'config.json').read_text());old['assignment_id']=aid
 mechanism='yield' if law.endswith('253') else 'caravan' if law.endswith('127-3') else old['mechanism'];old['mechanism']=mechanism
 rec=old['recording_description'];
 if mechanism in ('yield','caravan'):
  scalar='oncoming_x' if mechanism=='yield' else 'caravan_gap'
  if not any(x['name']==scalar for x in rec['channels']):rec['channels'].append(dict(name=scalar,unit='m',sampling_rate_hz=20,method='original native participant/body geometry scalar',time_window='full original trace',reference_frame='CARLA world',uncertainty='20 Hz temporal/body mesh approximation'))
 rec['limitations']=['Channels store measured physical evidence with explicit methods. Structured raw evidence does not assert legal meaning, intent, safety or hazard.','Native map geometry and authored legal-region assumptions remain distinguished.']
 for c in rec['channels']:
  c['method']='Original native actor telemetry/bounding boxes and authored road geometry, synchronized per original tick; value-free structured evidence for qualitative atoms'
  c['unit']='m/s' if c['name']=='kin.speed' else 'm' if c['name']=='kin.position' else 'structured physical evidence'
  c['uncertainty']='20 Hz temporal sampling; native mesh/body bounding-box approximation; unresolved legal interpretation'
 old['max_ticks']=2200;old['one_way']=d['cell']['layout']=='one_way_multilane'
 vars={'commanded_approach_speed':dict(kind='controller',value=5.,unit='m/s'),'commanded_turn_path':dict(kind='controller',value=d['cell']['maneuver']),'ego_speed':dict(kind='subject_behavior',value=None),'authored_context':dict(kind='world_setup',value={'public_highway':'explicit synthetic assumption','two_directional_highways':True,'witness_contexts':d['witness']['required_context']})}
 if law.endswith('400-2a'):primary='commanded_approach_lateral';values=[1.75,5.25];types=['compliant_attempt','violating_attempt'];rationale=['Approach in inner of two same-direction lanes adjacent to centreline','Approach in outer same-direction lane; no invented lateral legal cutoff']
 elif law.endswith('400-2b'):primary='commanded_exit_lateral';values=[1.75,-1.75];types=['compliant_attempt','violating_attempt'];rationale=['Leave in right-hand destination lane','Leave in destination opposing-direction lane to left of physical centreline']
 elif mechanism=='yield':primary='commanded_yield';values=[True,False];types=['compliant_attempt','violating_attempt'];rationale=['Hold subject already inside intersection until opposite-direction vehicle clears','Turn while opposite-direction vehicle remains in intersection; no immediate-hazard cutoff']
 elif mechanism=='caravan':primary='commanded_gap';values=[10.,20.,30.];types=['boundary_probe']*3;rationale=['Unlabeled fixed physical gap sweep; sufficient space and without danger remain unresolved']*3;vars['authored_context']['value'].update(outside_business_district='explicit external legal-region assumption',caravan_membership='explicit common-purpose assumption for ego and lead; merge actor is not a caravan member')
 elif mechanism=='lane_change':primary='commanded_signal';values=[True,False];types=['compliant_attempt','violating_attempt'];rationale=['Appropriate signal command precedes departure; safety fixed explicitly as synthetic assumption','No signal command while same lane-change controller and safety assumption retained'];vars['authored_context']['value']['movement_can_be_made_with_safety']='explicit fixed synthetic test assumption; not inferred from measurements'
 else:primary='commanded_halt';values=[True,False];types=['compliant_attempt','violating_attempt'];rationale=['Halt before near-side unmarked crosswalk','Cross near-side unmarked crosswalk without halt']
 vars[primary]=dict(kind='controller',value=values[0],unit='m' if isinstance(values[0],float) else 'boolean')
 judgments=[]
 if mechanism=='yield':judgments=[dict(phrase='immediate hazard',note=d['summary']['residue'][0])]
 if mechanism=='caravan':judgments=[dict(phrase='sufficient space',note=d['summary']['residue'][0]),dict(phrase='without danger',note=d['summary']['residue'][0])]
 if mechanism=='lane_change':judgments=[dict(phrase='ascertained that such movement can be made with safety',note=d['summary']['residue'][0])]
 cases=[dict(case_id=aid+'__baseline',target_law_id=None,target_type='baseline',rationale='Neutral definition only; never selected or simulated by default',variable_assignments=copy.deepcopy(vars),unresolved_judgment_calls=judgments,recording_description=rec)]
 for index,value in enumerate(values):
  va=copy.deepcopy(vars);va[primary]['value']=value
  case=dict(case_id=aid+'__'+('gap_'+str(int(value)) if mechanism=='caravan' else 'attempt_'+str(index)),target_law_id=law,target_type=types[index],rationale=rationale[index],variable_assignments=va,unresolved_judgment_calls=judgments,recording_description=rec,paired_probe_id=aid+'__comparison',deliberate_differences=[primary],probe=dict(primary_variable=primary,comparison_or_standard='physical geometry or explicit deterministic branch; no legal judgment cutoff',target_value_or_branch=value))
  if mechanism in ('yield','lane_change'):
   case['deterministic_branch']=dict(source_clause='which is within the intersection' if mechanism=='yield' else 'until the driver has given the appropriate turn signal',judgment_context=[dict(phrase=j['phrase'],note=j['note'],status='not_exercised' if mechanism=='yield' else 'fixed_assumption',reason='Oncoming vehicle is physically within intersection, so immediate-hazard alternative is not exercised' if mechanism=='yield' else 'Safety condition is fixed by authored test assumption; no physical measurement is claimed to establish it',world_setup_refs=[] if mechanism=='yield' else ['authored_context']) for j in judgments])
  cases.append(case)
 barriers=[]
 if mechanism=='stop':barriers=[dict(requirement='Rendered native stop sign whose governed lane and sidewalk-derived unmarked near-side crosswalk can be inspected',category='external_asset',evidence='Repository provides only OpenDRIVE metadata/reference mesh assumptions; no installed world inventory or rendered sidewalk/sign asset is supplied. CARLA is unavailable; OpenDRIVE signals alone are explicitly insufficient.',next_action='Supply native-map identity plus governed approach/crosswalk inventory from the dedicated CARLA environment. Bind the supplied native geometry and run the existing halt/no-halt controller after verification; do not substitute a painted stop line.',requires_live_execution=True)]
 if mechanism=='lane_change':barriers=[dict(requirement='Vehicle-native emitted indicator light calibration in the prescribed RGB view',category='live_measurement',evidence='No original RGB recording of the available Tesla asset exists in this repository. Native lamp bits cannot establish emitted illumination, and invented image regions would fabricate capability.',next_action='Inspect native rear right-indicator lamp mesh and original rear RGB view on the dedicated server; record visible right-indicator flash and freeze its image ROI/uncertainty before accepting this pair. Current native-bit channels and original encoded camera capture preserve that evidence.',requires_live_execution=True)]
 old['judgment_sweep_grid']=[6.,16.,26.,36.] if mechanism=='yield' else []
 old.update(supported_case_ids=[x['case_id'] for x in cases],default_case_id=cases[1]['case_id'],recording_description=rec,external_barriers=barriers,runtime_gaps=[],case=cases[1])
 # Frozen physical sweeps are retained alongside deterministic branches without adopting a judgment standard.
 sweeps=[]
 if judgments:
  sweeps=[dict(sweep_id=aid+'__judgment_physical_sweep',target_law_id=law,judgment_refs=judgments,status='complete' if mechanism in ('caravan','yield') else 'incomplete',mode='one_dimensional',variable_assignments=vars,recording_description=rec,rationale='Physical targets remain unlabeled; preserve exact judgment phrases and full raw histories')]
  if mechanism=='caravan':
   sweeps[0].update(axes=[dict(variable=primary,observable='caravan_gap',unit='m',min=10,max=30,spacing=10,measurement=dict(method='world-x bumper-surface gap between ego and lead from original body vertices',time_window='final 100 original samples before route completion',statistic='mean'),range_rationale='400m authored straight approaches, 7m two-lane half width and 4.8m blueprint-class body-length engineering estimate permit a merge vehicle between group members; native actual body lengths are checked during execution',spacing_rationale='10m physical spacing increments exceed the 2m engineering tracking tolerance and preserve distinct measured gaps',feasibility_evidence='Authored OpenDRIVE road extent and native vehicle bounding-box readback plus footprint/departure/collision checks in runner; no physical acceptance claimed before run')],landmarks=[])
  elif mechanism=='yield':
   sweeps[0].update(axes=[dict(variable='commanded_oncoming_x',observable='oncoming_x',unit='m',min=6,max=36,spacing=10,measurement=dict(method='first original oncoming body-centre world x on fixed opposite-direction route',time_window='first original recorded tick only',statistic='max'),range_rationale='The fixed junction extends to x=7; 6m tests its boundary context and 16/26/36m use the 393m east approach without map-end truncation. Ego is already inside. No value defines immediate hazard.',spacing_rationale='10m engineering station increments exceed vehicle body length and native 20Hz displacement, independent of legal interpretation or labels',feasibility_evidence='Authored 393m straight approaches and deterministic oncoming feedback route at 1m/s; first-frame readback, collision retention and footprint checks enforce actual realization')],landmarks=[])
  else:sweeps[0]['missing_inputs']=[dict(requirement='Frozen physical judgment sweep range validated against native first-run participant/camera measurements',category='live_measurement',evidence='No original run or calibrated visible-light/participant maneuver measurements supplied; deterministic branch and preserved raw channels do not establish judgment sweep feasibility',next_action='Execute deterministic authored configurations once; retain physical measured feasibility, then author a versioned fixed range without interpreting hazard or safety',requires_live_execution=True)]
 proposal=dict(cell_id=d['cell_id'],actor=d['actor'],status='draft',cases=cases,sweep_specs=sweeps)
 dump(w/'config.json',old);dump(w/'proposals/cases.json',proposal);(w/'runner.py').write_text((A/'runner_v3.txt').read_text());(w/'runner.py').chmod(0o755)
 for rel in shared:
  target=w/rel;target.parent.mkdir(exist_ok=True,parents=True);target.write_text((R/'work/_shared'/rel).read_text())
 (w/'tests/test_package.py').write_text((R/'work/_shared/tests/test_contracts.py').read_text()+extra_tests)
 plan=json.loads((w/'case-plan.json').read_text());plan.update(cases=cases,comparisons=[dict(case_ids=[x['case_id'] for x in cases[1:]],deliberate_differences=[primary],fixed_conditions=['authored map/props','physical actor blueprints','controller implementation and gains','camera poses/encoding/rate','all world_setup assignments'])],runtime_uncertainties=['CARLA unavailable; actual tracking, asset inventory, light emission, maneuver completion and source dependency versions remain first-run measurements.','Geometric occupancy and raw actor histories do not resolve a subjective judgment, statutory reference-point convention, shared purpose, intent, or public-highway status.'])
 if mechanism=='caravan':plan['runtime_uncertainties'].append('Body-length estimate is checked against actual bounding boxes, and each frozen gap retains collision/containment failures without range changes.')
 source_paths=['inputs/'+aid+'/assignment.json','runtime/stage-contracts.json','runtime/target-environment.json','runtime/worker_exchange/runtime_contract.py','runtime/python/pipeline_capture.py','examples/intersection/native/scene-stop257-v1.xodr','START_HERE.md','updates/003.json']+['work/_shared/'+x for x in shared]
 plan['sources']=[dict(path=p,sha256=sha(R/p)) for p in source_paths];dump(w/'case-plan.json',plan)
 template=json.loads((w/'proposals/template.json').read_text());template['structure']['judgment_calls_needed']=judgments;template['structure']['timing']['description']='; '.join(x['requirement'] for x in d['summary']['timing_requirements']);template['parameter_refs']=[dict(name=k,kind=v['kind'],range_or_domain='frozen physical case assignments; no legal judgment bound') for k,v in vars.items()];dump(w/'proposals/template.json',template)
 baseline=json.loads((w/'construction.json').read_text());baseline.update(recording_description=rec,mechanisms=['Physical two-directional OpenDRIVE road/marking builder','Observed-state bicycle steering and speed control with native actors; no teleportation','Per-frame required non-null raw physical channel projection and native full-body footprints','Four original RGB cameras encoded synchronously to VP9 WebM via shared Recording','Measured law-specific geometry/ordering/gap target checks and strict output acceptance','Termination signals, collision/departure failure retention, independent resource cleanup'],measurement_plan=dict(observables=rec['channels'],reference_geometry='geometry.json native map/road polygons and legal-region assumptions separately identified',target_tolerances='0.6m lane-position tracking; 2m gap tracking; engineering criteria only, no legal tolerance',first_run_finalization='Validate original-frame streams, 4 decoded videos/frame maps, actual participant/body geometry, output target checks and optional measured sweep summaries; preserve full recording and unresolved judgments'),static_checks=['runner.py --check','successful and failing full-output fixtures with encoded video','all materialized case bundle suites'],termination_rules=['native collision','measured body footprint outside physical road surface','original time budget','route completion','SIGINT/SIGTERM','capture/runtime error; all owned resources independently cleaned'])
 # Remove obsolete construction proposals while preserving their old content as migration evidence.
 obsolete=list((w/'constructions').glob('*.json'))
 for p in obsolete:
  archive=w/'prior-v2'/p.name;archive.parent.mkdir(exist_ok=True);archive.write_text(p.read_text());p.unlink()
 common=['runner.py','road-template.xodr','proposals/cases.json']+shared+[x for x in ['scenario.py','finalize.py'] if (w/x).exists()]
 for i,case in enumerate(cases[1:]):
  case_config=copy.deepcopy(old);case_config['default_case_id']=case['case_id'];case_config['case']=case
  con=copy.deepcopy(baseline);con['case_id']=case['case_id'];con['files']=[]
  for rel in common:
   e=dict(path=rel,content=(w/rel).read_text())
   if rel in shared:e['source']='work/_shared/'+rel
   con['files'].append(e)
  con['files'].append(dict(path='config.json',content=json.dumps(case_config,indent=2)+'\n'))
  if i==0:dump(w/'config.json',case_config);dump(w/'construction.json',con)
  else:dump(w/('constructions/'+case['case_id']+'.json'),con)
 dump(w/'update-acknowledgements.json',dict(applied_update=3,acknowledgements=[dict(version=2,action='continue',status='applied'),dict(version=3,action='continue',status='applied',note='Continued original packages; shared recording/contracts, law-specific controllers and materialized fixture acceptance implemented')]))
 blocked=barriers+([x for s in sweeps if s['status']=='incomplete' for x in s['missing_inputs']])
 status='blocked' if blocked else 'ready'
 tests=[]
 for tag,cmd in [('check',['python3.11',str(w.relative_to(R)/'runner.py'),'--check']),('tests',['python3.11','-m','unittest','discover','-s',str(w.relative_to(R)/'tests')])]:
  p=subprocess.run(cmd,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,env=dict(__import__('os').environ,PYTHONPATH=str(w)));log=w/('logs/v3-'+tag+'.log');log.write_text(p.stdout);tests.append(dict(command=' '.join(cmd),exit_code=p.returncode,log=str(log.relative_to(w)),sha256=sha(log)))
 result=dict(assignment_id=aid,input_sha256=sha(R/'inputs'/aid/'assignment.json'),status=status,applied_update=3,tests=tests,externally_blocked_requirements=blocked,runtime_uncertainties=plan['runtime_uncertainties'])
 if blocked:result['reason']='; '.join(x['requirement'] for x in blocked)
 if any(t['exit_code'] for t in tests):result['status']='partial';result['reason']='Offline fixture validation failed; implementation repair in progress.'
 dump(w/'result.json',result)
 (w/'HANDOFF.md').write_text('# '+result['status']+' executable preparation\n\nUpdate 003 continues the retained packages, replacing generic capability comparisons with law-specific branch configurations. Baseline remains unselected. Exact supplied laws, cells, actor, witness, summaries and existing evidence remain preserved in input and case-plan source hashes.\n\nRun `python3.11 runner.py --check`; live entrypoint: `python3 runner.py --output-dir PATH --host HOST --port PORT --case-id ID`. No live case was run here. The runner controls actual native actors, records full original-frame PipelineCapture plus four VP9 WebM views and mandatory non-null raw evidence channels, and returns zero only after strict measured output acceptance. Raw qualitative-channel values preserve geometry/participant evidence and never resolve a legal predicate or mental state.\n\n'+ '\n'.join('- '+x['case_id']+': '+x['rationale'] for x in cases)+'\n\nAdditional canonical proposals (each has its own inline config and identical implementation):\n'+ '\n'.join('- `constructions/'+x['case_id']+'.json`' for x in cases[2:])+'\n\n'+('\n'.join('- External barrier: '+x['requirement']+' — '+x['evidence']+' Next: '+x['next_action'] for x in blocked) if blocked else 'All non-GPU construction, recording and acceptance paths are implemented. Native physics and inventory remain explicit first-run uncertainties, not simulated evidence.')+'\n\nFinalization: preserve the full original trace and synchronized videos. Validate all required participants, non-null channels, declared rates, footprints, measured geometry/ordering/gap targets, decoded video counts, original timestamps and cleanup. Inspect original footage for physical meaning. Summaries use actual original samples in the frozen declared window and are recomputable from raw streams. Keep synthetic legal-region/shared-purpose assumptions separate. Failed native tracking or missing assets retain their evidence and require cause-based repair at the frozen setting. Judgment sweeps remain unlabeled; no legal threshold, verdict, or physical acceptance is claimed.\n\nText/summary conflicts: the exact stop law supplies no fixed stationary span, so no legal minimum duration is introduced. The caravan summary describes common purpose using queue behavior, but membership is retained as a separate external assumption. The 400-2b summary adopts a footprint convention beyond the exact quote; full body vertices and body-centre measures are both retained without resolving that convention.\n')
 print(aid,result['status'],[(t['exit_code']) for t in tests])
