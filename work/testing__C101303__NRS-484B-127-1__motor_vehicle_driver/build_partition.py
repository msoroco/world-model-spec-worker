import copy,hashlib,json,pathlib,subprocess
R=pathlib.Path('.');HOME=R/'work/testing__C101303__NRS-484B-127-1__motor_vehicle_driver'
IDS=json.loads((R/'partitions/demo-test-04.json').read_text())['assignment_ids']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def var(kind,value,unit=None):return dict(kind=kind,value=value,**({'unit':unit} if unit else {}))
for aid in IDS:
 a=json.loads((R/'inputs'/aid/'assignment.json').read_text());d=R/'work'/aid;d.mkdir(parents=True,exist_ok=True);law=a['law_id'];mode={'NRS-484B-127-1':'following','NRS-484B-600-1e':'alley','NRS-484B-600-1c':'posted','NRS-484B-307-6a':'signal','NRS-484B-250-4':'inoperative'}[law]
 atoms=list(dict.fromkeys([o['atom'] for o in a['summary']['required_observations']]+['kin.speed','kin.position']))
 desc={'channels':[{'name':n,'unit':'m/s' if n=='kin.speed' else 'm' if n=='kin.position' else 'raw','sampling_rate_hz':20,'method':'native velocity norm' if n=='kin.speed' else 'native original-frame evidence packet; semantic projection remains draft','time_window':'entire original execution','reference_frame':'native CARLA world XYZ','uncertainty':'50ms acquisition interval; semantic and physical feature audit unconfirmed'} for n in atoms], 'context_inputs':[{'name':'authored_context','unit':'object','method':'retained synthetic assumptions and exact required witness context'}], 'limitations':['Physical raw evidence packets do not establish every named semantic atom. No legal verdict, intent, authority provenance or judgment cutoff is inferred.']}
 assumptions={'public_highway':'synthetic test assumption; not inferred from rendering','physical_driver':'modeled controller acting on conventional passenger vehicle','official_devices':'native asset identity is not proof of public legal authority','witness_required_context':a['witness']['required_context']}
 if mode=='inoperative':assumptions.update(caution_context='fixed synthetic assumption for deterministic halt-only branch; not measured caution',post_stop_yield='fixed synthetic condition; separate interaction branches remain unfinished')
 base={'commanded_approach_speed':var('controller',8,'m/s'),'commanded_turn_path':var('controller','change_lane' if mode=='following' else 'travel'),'ego_speed':var('subject_behavior',None,'m/s'),'authored_context':var('world_setup',assumptions)}
 if mode=='following':base['commanded_following_gap']=var('controller',30,'m');base['observed_following_gap']=var('subject_behavior',None,'m')
 if mode=='inoperative':base['commanded_halt']=var('controller',True)
 if mode=='signal':base['obey_red']=var('controller',True)
 threshold=80 if mode=='alley' else 25
 if mode=='posted':base['posted_speed_limit']=var('world_setup',threshold,'mph')
 cases=[];comparisons=[]
 def case(suffix,typ,updates,rationale):
  v=copy.deepcopy(base)
  for k,val in updates.items():v[k]['value']=val
  return {'case_id':aid+'__'+suffix,'target_law_id':None if typ=='baseline' else law,'target_type':typ,'rationale':rationale,'variable_assignments':v,'unresolved_judgment_calls':[], 'recording_description':desc}
 cases.append(case('baseline','baseline',{},'Neutral unselected baseline; no simulation requested.'))
 refs=[]
 if mode=='following':refs=[{'phrase':'reasonable and prudent','note':a['summary']['residue'][0]}]
 if mode=='inoperative':refs=[{'phrase':'proceed cautiously','note':a['summary']['residue'][0]}]
 if mode in ('alley','posted'):
  for label,mph in [('below',threshold-5),('at',threshold-.5),('above',threshold+5)]:
   c=case(label,'boundary_probe',{'commanded_approach_speed':mph*.44704},'Statutory speed probe; at is commanded 0.5mph inside compliant side, not equality. Measured speed controls later classification.')
   c.update(paired_probe_id=aid+'__speed_triple',deliberate_differences=['commanded_approach_speed'],probe={'primary_variable':'commanded_approach_speed','comparison_or_standard':'statutory speed maximum','target_value_or_branch':mph*.44704,'threshold_ref':law if mode=='alley' else 'posted_speed_limit','operator':'<=','unit':'m/s','test_value':mph*.44704,'epsilon_used':.5*.44704,'threshold_value':threshold*.44704})
   cases.append(c)
 elif mode in ('signal','inoperative'):
  key='obey_red' if mode=='signal' else 'commanded_halt'
  for suffix,typ,value in [('observe_rule','compliant_attempt',True),('omit_required_action','violating_attempt',False)]:
   c=case(suffix,typ,{key:value},'Compare original physical '+('red-entry avoidance versus entry while red after yellow' if mode=='signal' else 'complete halt before marked line versus no halt; post-stop caution fixed explicitly')+'. No actual outcome is assumed.')
   c.update(paired_probe_id=aid+'__action_pair',deliberate_differences=[key],probe={'primary_variable':key,'comparison_or_standard':'plain statutory action branch','target_value_or_branch':value})
   if refs:c['deterministic_branch']={'source_clause':'shall stop at a clearly marked stop line','judgment_context':[dict(r,status='fixed_assumption',reason='Halt-only branch with post-stop caution explicitly fixed as synthetic context; not a physical measurement',world_setup_refs=['authored_context']) for r in refs]}
   c['unresolved_judgment_calls']=refs;cases.append(c)
 else:
  # Capability probes are kept separate from canonical judgment sweep expansion.
  for gap in (15,30,45):
   c=case('gap_capability_'+str(gap),'boundary_probe',{'commanded_following_gap':gap},'Physical controller capability only; not an accepted judgment sweep point or anticipated compliance label.')
   c.update(paired_probe_id=aid+'__gap_capability',deliberate_differences=['commanded_following_gap'],probe={'primary_variable':'commanded_following_gap','comparison_or_standard':'engineering gap tracking capability; reasonable/prudent remains unresolved','target_value_or_branch':gap});c['unresolved_judgment_calls']=refs;cases.append(c)
 if len(cases)>2:comparisons=[{'case_ids':[c['case_id'] for c in cases[1:]],'deliberate_differences':cases[1]['deliberate_differences'],'fixed_conditions':['identical runner/map/camera/controller implementation, physics, weather, actor blueprints, initial subject transform, route and timing','authored law context except explicitly changed scalar assignment'],'status':'draft'}]
 gaps=['Semantic projection of all required atoms from raw original-frame packets is unfinished; packets are retained rather than fabricated observations.','Full rendered feature/indicator visibility and per-atom interpretation need a native first-run audit; no legal acceptance claimed.']
 if mode=='alley':gaps+=['Authored 2400m two-way 6m surface is executable but alley legal/context designation, actual marked access aisle and adjacent built form are not realized; implement these physical features or bind a surveyed alley before first-run readiness.']
 if mode=='posted':gaps+=['Native speed-sign discovery is implemented; full particular-highway-portion governance and narrow-road extent require a reviewed native binding; dynamic get_speed_limit is not authority evidence.']
 if mode=='following':gaps+=['Gap feedback, grade crest and smooth lane-change controllers are implemented; measured feasible gap range and lane-change body containment still need validation. Canonical judgment sweep remains incomplete, capability probes are not accepted sweep delivery.']
 if mode=='signal':gaps+=['Native route discovery verifies a signal-governed junction; strict one-way approach, two-way destination, exact entry footprint boundary, and official head provenance need a reviewed native binding.']
 if mode=='inoperative':gaps+=['Native Off/frozen signal control and halt/no-halt controller implemented. Clear stop-line mesh, blind obstructions, earlier-stopped/occupying separate vehicles and all-entrance history interactions are not implemented; native binding required.','Nine-point sight capture auto-enables from required atom but incoming-lane 230m coverage is not statically certified on a discovered native route.']
 sweeps=[]
 for ref in refs:
  sweeps.append({'sweep_id':aid+'__'+ref['phrase'].replace(' ','_'),'target_law_id':law,'judgment_refs':[ref],'status':'incomplete','mode':'one_dimensional','axes':[],'landmarks':[],'rationale':'Freeze no purported legal standard or unverified physics range. Executable capability configuration is separate from accepted sweep selection.','variable_assignments':base,'recording_description':desc,'missing_inputs':gaps})
 cfg={'assignment_id':aid,'law_id':law,'cell_id':a['cell_id'],'actor':a['actor'],'delivery_status':'partial','mode':mode,'supported_case_ids':[c['case_id'] for c in cases],'default_case_id':cases[1]['case_id'],'baseline_selected':False,'cases':cases,'duration_s':45 if mode in ('alley','posted','following') else 25,'maximum_speed_mps':(threshold+5)*.44704 if mode in ('alley','posted') else 15,'threshold_mph':threshold,'measurement_window_s':[15,24] if mode in ('alley','posted','following') else [2,3],'capture_hz':20,'required_atoms':atoms,'required_context':a['witness']['required_context'],'recording_description':desc,'runtime_gaps':gaps,'cameras':[{'x':-8,'z':4,'pitch':-15,'width':1920,'height':1080},{'x':.7,'y':-.3,'z':1.5,'pitch':0,'width':1280,'height':720},{'x':-2,'z':16,'pitch':-80,'width':1280,'height':720},{'x':-4,'y':4,'z':2,'pitch':-5,'yaw':-30,'width':1280,'height':720}]}
 write(d/'config.json',cfg);(d/'runner.py').write_text((HOME/'runner_template.py').read_text());(d/'runner.py').chmod(0o755);(d/'road-template.xodr').write_text((R/'examples/numeric/native/scene.xodr').read_text())
 template={'template_id':law+'@'+a['actor'],'law_id':law,'actor':a['actor'],'quote':a['law']['text'],'structure':{'law_id':law,'activation':{'condition':'; '.join(a['summary']['activation_conditions']),'numeric_conditions':[]},'obligation':{'description':a['law']['text'],'type':'must_not' if mode in ('alley','posted','signal') else 'must','numeric_conditions':[{'variable':'ego_speed','operator':'<=','value':threshold if mode=='alley' else 'posted_speed_limit','unit':'mph'}] if mode in ('alley','posted') else []},'exceptions':[],'timing':{'description':a['summary']['timing_requirements'],'numeric_conditions':[]},'judgment_calls_needed':refs},'parameter_refs':[{'name':k,'kind':v['kind'],'range_or_domain':'recorded only' if v['kind']=='subject_behavior' else 'exact draft case assignments'} for k,v in base.items()]}
 write(d/'proposals/template.json',template)
 write(d/'proposals/relevance.json',{'cell_id':a['cell_id'],'actor':a['actor'],'status':'draft','relevant_laws':[{'law_id':law,'quote':a['law']['text'],'applies_to':[a['actor']],'relevance_type':'specific_match','confidence':'medium','notes':'Exact assigned scope; no additional laws selected. Witness context remains conditional until physically established.'}],'borderline_excluded':[]})
 write(d/'proposals/bindings.json',{'cell_id':a['cell_id'],'actor':a['actor'],'status':'draft','established_contexts':['synthetic assumptions in authored_context; physical verification remains pending'],'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],'context_refs':[],'fixed_parameters':[{'name':'cell_layout','value':a['cell']['layout'],'rationale':'supplied exact cell'}],'variable_parameters':[{'name':k,'kind':v['kind'],'range_or_domain':'exact case assignments','used_by_laws':[law]} for k,v in base.items()]})
 write(d/'proposals/judgment-observables.json',[{'template_id':template['template_id'],'phrase':ref['phrase'],'note':ref['note'],'status':'draft','observable_requirements':{'observables':[{'name':n,'unit':'raw','description':next((x['note'] for x in a['summary']['required_observations'] if x['atom']==n),'native motion capture')} for n in atoms],'context_inputs':[{'name':'authored_context','unit':'object','description':'factual context, never a chosen judgment bound'}],'sweep_dimensions':[{'name':'commanded_following_gap' if mode=='following' else 'commanded_approach_speed','unit':'m' if mode=='following' else 'm/s','description':'physical controller target, not judgment value'}],'landmarks':[],'recording_needs':[{'name':n,'unit':'raw','description':'full synchronized original history'} for n in atoms],'limitations':['Legal interpretation and mental states remain unresolved.']}} for ref in refs])
 write(d/'proposals/cases.json',{'cell_id':a['cell_id'],'actor':a['actor'],'status':'draft','cases':cases,'sweep_specs':sweeps})
 sources=[{'path':str(p),'sha256':sha(p)} for p in [R/'inputs'/aid/'assignment.json',R/'runtime/stage-contracts.json',R/'runtime/target-environment.json',R/'runtime/python/pipeline_capture.py',R/'runtime/python/original_observations.py',R/'examples/numeric/native/scene.xodr',R/'updates/002.json']]
 write(d/'case-plan.json',{'assignment_id':aid,'law_id':law,'cell_id':a['cell_id'],'actor':a['actor'],'cases':cases,'comparisons':comparisons,'observations':[{'name':n,'mandatory':True} for n in atoms],'sources':sources,'existing_evidence':a['existing_evidence'],'runtime_uncertainties':gaps+['Python3.8 CARLA0.9.15 native API, blueprint availability and ffmpeg encoding not tested here; offline tests use Python3.11.','Live measured-results finalization must retain trace and raw streams, recompute frozen [15,24] speed mean, use 0.5mph tracking engineering tolerance, review full RGB/frame mapping and device/geometry cause evidence. No target setpoint may replace measurements.']})
 def construction(c):
  own=copy.deepcopy(cfg);own['default_case_id']=c['case_id']
  return {'cell_id':a['cell_id'],'actor':a['actor'],'case_id':c['case_id'],'status':'draft','files':[{'path':'runner.py','content':(d/'runner.py').read_text()},{'path':'config.json','content':json.dumps(own,indent=2)+'\n'},{'path':'road-template.xodr','content':(d/'road-template.xodr').read_text()},{'path':'proposals/cases.json','content':(d/'proposals/cases.json').read_text()}],'entrypoint':'runner.py','mechanisms':['original-run physical vehicle feedback controller',mode+' geometry/native-device configuration','four original RGB encoders and PipelineCapture per tick'],'measurement_plan':{'speed':{'method':'native velocity norm','window_s':cfg['measurement_window_s'],'statistic':'mean','engineering_tracking_tolerance_mps':.5*.44704},'gaps':'physical world-space body vertex projected separation; not centre-point distance','unsupported':gaps},'recording_description':desc,'static_checks':['--check verifies scope, baseline nonselection, speed policy, road extent and canonical assignment kinds','unittest checks wrapped heading, actuator braking, footprint gap and observed-window summary'],'termination_rules':{'duration_s':cfg['duration_s'],'signals':['SIGINT','SIGTERM'],'events':['collision','loss of control','capture/encoder mismatch','timeout'],'cleanup':'owned actors/sensors, original signals/weather/world settings; no server shutdown'}}
 anchor=construction(cases[1]);anchor['files'][1]['content']=(d/'config.json').read_text();write(d/'construction.json',anchor)
 for c in cases[2:]:write(d/'constructions'/(c['case_id']+'.json'),construction(c))
 write(d/'update-acknowledgements.json',{'assignment_id':aid,'applied_update':2,'notices':[{'version':2,'action':'continue','status':'applied','instructions':'Full six-step trial; implementations and CPU tests completed with explicit partial residuals.'}],'paused':False})
 (d/'tests').mkdir(exist_ok=True)
 (d/'tests/test_package.py').write_text('''import importlib.util,pathlib,unittest,json,math
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('runner_'+P.name,P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class TestPackage(unittest.TestCase):
 def test_offline(self):m.offline_check()
 def test_brake(self):self.assertGreater(m.control(0,0,0,15,[(x,0) for x in range(100)],3)['brake'],0)
 def test_heading_wrap(self):self.assertEqual(m.heading_error(359,1),2)
 def test_gap_uses_footprints(self):self.assertEqual(m.physical_gap([[0,0],[4,0]],[[20,0],[24,0]],[1,0]),16)
 def test_window_excludes_acceleration(self):
  s=m.summarize([dict(time_s=1,value=100),dict(time_s=16,value=3),dict(time_s=20,value=5)],15,24);self.assertEqual(s['mean'],4);self.assertEqual(s['sample_window_s'],[16,20])
 def test_empty_window_rejected(self):
  with self.assertRaises(ValueError):m.summarize([],15,24)
 def test_canonical_inline(self):
  p=json.loads((P/'construction.json').read_text())
  for f in p['files']:self.assertEqual((P/f['path']).read_text(),f['content'])
 def test_no_target_as_observation(self):
  c=json.loads((P/'config.json').read_text())
  for case in c['cases']:
   for v in case['variable_assignments'].values():
    if v['kind']=='subject_behavior':self.assertIsNone(v['value'])
''')
 tests=[]
 for name,cmd in [('check',['python3.11',str(d/'runner.py'),'--check']),('unittest',['python3.11','-m','unittest','discover','-s',str(d/'tests')])]:
  proc=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);p=d/'logs'/(name+'.log');p.parent.mkdir(exist_ok=True);p.write_text(proc.stdout);tests.append({'command':' '.join(cmd),'exit_code':proc.returncode,'log':str(p.relative_to(d)),'sha256':sha(p)})
 write(d/'result.json',{'assignment_id':aid,'input_sha256':sha(R/'inputs'/aid/'assignment.json'),'status':'partial','applied_update':2,'reason':'; '.join(gaps),'tests':tests,'six_steps':{'inputs':'exact law/cell/actor/witness/summary/evidence read','cases':'draft statutory triple/action pairs or incomplete judgment sweep plus explicit capability cases','implementation':'executable physical controller/geometry/native discovery/camera runner','checks':'geometry, original-frame capture, measured raw speed/gap, cleanup and explicit unsupported semantics','offline_tests':'eight tests and --check per package','handoff':'runtime uncertainties and measured-results finalization documented'}})
 (d/'HANDOFF.md').write_text('''# Executable preparation: partial

This package includes exact-scope draft semantic proposals, physical vehicle feedback control, authored map generation or native signal/sign route discovery, four synchronized RGB encoders, original-frame PipelineCapture, required-channel raw packets, observed speed/gap summaries, signal handling and restoration. No simulator was run.

Baseline is a neutral unselected definition. Run `python3.11 runner.py --check`; live use `python3 runner.py --output-dir PATH --host HOST --port PORT --case-id CASE_ID` from this directory. The executor must provide CARLA 0.9.15, Python3.8-compatible dependencies, ffmpeg and a dedicated resource lease. Runtime imports are lazy. The runner preserves failed results and returns nonzero while semantic capability is partial.

'''+ '\n'.join('- '+g for g in gaps)+'''

The root construction anchors the first active case. Additional canonical proposals (same implementation, case-specific config.json) are:

'''+ '\n'.join('- constructions/'+c['case_id']+'.json' for c in cases[2:])+'''

Finalization: retain the complete original trace, recorder, road.xodr, native graphs/evidence, raw per-channel packets, four full RGB videos and zero-based frame map. Recompute speed/gap summaries only from saved actual samples in frozen windows. The 0.5mph speed criterion is engineering tracking tolerance. Validate native geometry/device governance, full body entry, all relevant traffic histories, visibility and each required atom; missing semantic capability is a repair requirement, not data to fabricate. Review synchronized full videos before any downstream labeling. Keep judgment phrases unresolved; do not treat capability probes as accepted judgment sweep coverage. Repair the same frozen setting with evidence-backed code changes; never retrospectively change range/targets or silently retry unchanged code.

Tests are CPU-only; result.json records exact commands, exit codes and hashed logs. Sources and existing evidence are retained in case-plan.json. Update 002 applied; no pause was active.
''')
 print(aid,[(t['exit_code'],t['command']) for t in tests])
