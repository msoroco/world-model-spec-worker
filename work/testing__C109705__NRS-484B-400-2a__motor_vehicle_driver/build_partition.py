import json, pathlib, hashlib, subprocess, copy
R=pathlib.Path.cwd()
IDS=json.loads((R/'partitions/demo-test-01.json').read_text())['assignment_ids']
def dump(p,d): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2)+'\n')
runner='''#!/usr/bin/env python3
"""Draft original-frame physical controller; no legal verdict or invented evidence."""
import argparse,json,math,pathlib,sys,signal,queue,xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parent

def speed(v): return math.sqrt(v.x*v.x+v.y*v.y+v.z*v.z)
def command(position,yaw,velocity,path,target):
    closest=min(range(len(path)),key=lambda i:math.hypot(path[i][0]-position[0],path[i][1]-position[1]))
    goal=path[min(closest+4,len(path)-1)]
    error=(math.atan2(goal[1]-position[1],goal[0]-position[0])-math.radians(yaw)+math.pi)%(2*math.pi)-math.pi
    effort=.45*(target-velocity)
    return dict(throttle=max(0,min(.65,effort)),brake=max(0,min(1,-effort)),steer=max(-.8,min(.8,1.4*error)))
def build_road():
    tree=ET.parse(ROOT/'road-template.xodr');root=tree.getroot();root.find('header').set('name','partition1-draft')
    if json.loads((ROOT/'config.json').read_text())['mechanism']!='stop':
        for road in root.findall('road'):
            for tag in ('objects','signals'):
                node=road.find(tag)
                if node is not None: road.remove(node)
    return ET.tostring(root,encoding='unicode')
def check():
    c=json.loads((ROOT/'config.json').read_text());p=json.loads((ROOT/'proposals/cases.json').read_text())
    assert set(c['supported_case_ids'])=={x['case_id'] for x in p['cases']}
    assert len(c['path'])>10 and all(len(x)==2 for x in c['path'])
    assert all(math.dist(a,b)<4 for a,b in zip(c['path'],c['path'][1:]))
    assert len(ET.fromstring(build_road()).findall('road'))==6
    assert not any(x.get('expected_label') for x in p['sweep_specs'])
    print('Offline configuration, road, route continuity and case checks passed; runtime unconfirmed')
def run(args):
    import carla
    c=json.loads((ROOT/'config.json').read_text());cases={x['case_id']:x for x in json.loads((ROOT/'proposals/cases.json').read_text())['cases']}
    case=cases[args.case_id or c['default_case_id']]
    if case['target_type']=='baseline': raise ValueError('Baseline is definition-only; select a physical target case')
    out=pathlib.Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists():raise FileExistsError('Retain prior attempt; choose a fresh output directory')
    client=carla.Client(args.host,args.port);client.set_timeout(30)
    if client.get_client_version()!=client.get_server_version():raise RuntimeError('Client/server version mismatch')
    # Authored map loading requires the executor dedicated resource lease.
    world=client.generate_opendrive_world(build_road());old=world.get_settings();actors=[];cap=None;stop=[False];frames=0
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.__setitem__(0,True))
    result=dict(setup_confirmed=False,behavior_attempted=False,maneuver_completed=False,termination_reason='setup_failure',physical_failure_flags=[],measured_values={},target_checks=[],recording_description=c['recording_description'],recording_evidence=[],realized_observables={},trace_reference='trace.jsonl',video_references=[],video_frame_map_reference='video_frame_map.jsonl',requested_variable_assignments=case['variable_assignments'])
    streams=[]
    try:
        settings=world.get_settings();settings.synchronous_mode=True;settings.fixed_delta_seconds=.05;world.apply_settings(settings)
        bp=world.get_blueprint_library().find('vehicle.tesla.model3');p=c['path'][0]
        ego=world.spawn_actor(bp,carla.Transform(carla.Location(x=p[0],y=p[1],z=.5),carla.Rotation(yaw=0)));actors.append(ego)
        sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))
        from pipeline_capture import PipelineCapture
        (out/'config.json').write_text(json.dumps(c))
        cap=PipelineCapture(client,ego,out,case['case_id'],required_observations=c['required_atoms'])
        cameras=[]
        for i,pose in enumerate(c['cameras']):
            cbp=world.get_blueprint_library().find('sensor.camera.rgb');cbp.set_attribute('image_size_x',str(pose['width']));cbp.set_attribute('image_size_y',str(pose['height']));cbp.set_attribute('sensor_tick','0.05')
            cam=world.spawn_actor(cbp,carla.Transform(carla.Location(x=pose['x'],z=pose['z']),carla.Rotation(pitch=pose['pitch'])),attach_to=ego);actors.append(cam);q=queue.Queue();cam.listen(q.put);cameras.append((cam,q,i));(out/('rgb'+str(i))).mkdir()
        fmap=(out/'video_frame_map.jsonl').open('x');streams.append(fmap)
        raw=(out/'kin.speed.jsonl').open('x');streams.append(raw)
        result['behavior_attempted']=True
        for tick in range(c['max_ticks']):
            if stop[0]:result['termination_reason']='signal';break
            t=ego.get_transform();v=speed(ego.get_velocity());target=case['variable_assignments']['commanded_approach_speed']['value']
            if c['mechanism']=='stop' and case['variable_assignments'].get('commanded_halt',{}).get('value') and t.location.x>-25 and t.location.x<-10:target=min(target,math.sqrt(2*1.5*max(0,-14-t.location.x)))
            control=command((t.location.x,t.location.y),t.rotation.yaw,v,c['path'],target);ego.apply_control(carla.VehicleControl(**control))
            frame=world.tick();snap=world.get_snapshot();time_s=snap.timestamp.elapsed_seconds
            cap.capture(frame,time_s,extra={'ego_lamp_bits':int(ego.get_light_state())})
            for cam,q,i in cameras:
                im=q.get(timeout=15)
                while im.frame<frame:im=q.get(timeout=15)
                if im.frame!=frame:raise RuntimeError('Camera/frame mismatch')
                im.save_to_disk(str(out/('rgb'+str(i))/('%06d.png'%frames)))
            fmap.write(json.dumps(dict(video_frame=frames,carla_frame=frame,time_s=time_s))+'\\n');raw.write(json.dumps(dict(time_s=time_s,value=speed(ego.get_velocity())))+'\\n');frames+=1
            end=c['path'][-1]
            if math.hypot(t.location.x-end[0],t.location.y-end[1])<2:result['maneuver_completed']=True;result['termination_reason']='route_end';break
        else:result['termination_reason']='timeout'
        result['measured_values']={'captured_frames':frames};result['recording_evidence']=[dict(name='kin.speed',unit='m/s',reference='kin.speed.jsonl')]
        result['physical_failure_flags'].append('mandatory_atom_streams_and_law_specific_setup_not_finalized')
    except Exception as exc:
        result['physical_failure_flags'].append(type(exc).__name__+': '+str(exc));result['termination_reason']='runtime_failure'
    finally:
        if cap is not None:cap.close(confirmed=False)
        for stream in streams:stream.close()
        for actor in reversed(actors):
            if hasattr(actor,'stop'):actor.stop()
            actor.destroy()
        world.apply_settings(old)
        (out/'result.json').write_text(json.dumps(result,indent=2))
    return 2 # Draft: missing setup/observation acceptance never counts as successful execution.
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');ap.add_argument('--output-dir');ap.add_argument('--host',default='127.0.0.1');ap.add_argument('--port',type=int,default=2000);ap.add_argument('--case-id');a=ap.parse_args()
    if a.check:check()
    elif not a.output_dir:ap.error('--output-dir required')
    else:sys.exit(run(a))
'''
tests='''import importlib.util,pathlib,unittest,math
P=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('draft_runner',P/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_offline(self):m.check()
 def test_braking(self):self.assertGreater(m.command((0,0),0,10,[(i,0) for i in range(20)],2)['brake'],0)
 def test_heading_wrap(self):self.assertLess(abs(m.command((0,0),359,2,[(i,0) for i in range(20)],2)['steer']),.1)
 def test_saturation(self):
  c=m.command((0,0),180,0,[(i,0) for i in range(20)],30);self.assertLessEqual(c['throttle'],.65);self.assertLessEqual(abs(c['steer']),.8)
 def test_speed(self):
  class V:x=3;y=4;z=0
  self.assertEqual(m.speed(V()),5)
'''
for aid in IDS:
 d=json.loads((R/'inputs'/aid/'assignment.json').read_text());w=R/'work'/aid;w.mkdir(parents=True,exist_ok=True);law=d['law_id'];summary=d['summary'];judgment=summary['tier'] in ('Q','S');mechanism='turn' if d['cell']['maneuver']=='left_turn' else 'lane_change' if d['cell']['maneuver']=='lane_change' else 'stop' if law=='NRS-484A-450-2' else 'follow'
 # CARLA coordinates: reflected OpenDRIVE y. All physical routes use the supplied broad intersection operating surface.
 path=[[-80+i,1.75] for i in range(71)]
 if mechanism=='turn':
  path += [[-10+11.75*__import__('math').sin(i*__import__('math').pi/2/20),1.75-11.75*(1-__import__('math').cos(i*__import__('math').pi/2/20))] for i in range(1,21)]
  path += [[1.75,-10-i] for i in range(1,51)]
 elif mechanism=='lane_change':path += [[-10+i,1.75+3.5*(.5-.5*__import__('math').cos(min(i/30,1)*__import__('math').pi))] for i in range(1,71)]
 else:path += [[-10+i,1.75] for i in range(1,71)]
 atoms=[x['atom'] for x in summary['required_observations']]
 rec={'channels':[dict(name=x,unit='m/s' if x=='kin.speed' else 'raw',sampling_rate_hz=20,method='original-frame PipelineCapture raw evidence; atom projection pending',time_window='entire original run',reference_frame='CARLA world',uncertainty='not yet characterized; no legal tolerance') for x in atoms],'context_inputs':[dict(name='authored_context',unit='object',method='config.json exact assumptions and source witness')],'limitations':['Raw graphs are not finalized per-atom JSONL channels; first-run readiness is partial.']}
 variables={'commanded_approach_speed':dict(kind='controller',value=5,unit='m/s'),'commanded_turn_path':dict(kind='controller',value=d['cell']['maneuver']),'ego_speed':dict(kind='subject_behavior',value=None),'authored_context':dict(kind='world_setup',value={'public_highway':'explicit synthetic assumption','witness_contexts':d['witness']['required_context']})}
 cases=[]
 for name,tt,value in [('baseline','baseline',5),('probe_low','boundary_probe',3),('probe_high','boundary_probe',7)]:
  va=copy.deepcopy(variables);va['commanded_approach_speed']['value']=value
  case=dict(case_id=aid+'__'+name,target_law_id=None if name=='baseline' else law,target_type=tt,rationale='Neutral definition, unselected' if name=='baseline' else 'Physical capability probe only; no legal threshold or outcome asserted',variable_assignments=va,unresolved_judgment_calls=summary['residue'],recording_description=rec)
  if name!='baseline':case.update(paired_probe_id=aid+'__speed_comparison',deliberate_differences=['commanded_approach_speed'],probe=dict(primary_variable='commanded_approach_speed',comparison_or_standard='engineering capability only; legal applicability unresolved',target_value_or_branch=value))
  cases.append(case)
 gaps=['Per-atom JSONL projection, exact law-specific setup validation and physical-cause target checks remain unimplemented; raw capture alone is insufficient.']
 if mechanism=='turn':gaps+=['Left-turn connectivity/footprint containment requires authored curved junction connectors; reference map contains straight connectors only.','Approach lateral-position and destination-side comparison branches require controller configuration beyond the speed capability probes.']
 if mechanism=='lane_change':gaps+=['Appropriate signal timing, emitted indicator visibility and interacting target-lane participant controller are not implemented.']
 if mechanism=='follow':gaps+=['Caravan membership is an explicit external assumption, not inferred from queue motion. Consecutive group vehicles, merging vehicle and gap controller remain unimplemented.']
 if mechanism=='stop':gaps+=['Physical stop-sign governed lanes and near-side unmarked crosswalk derived from rendered sidewalk boundaries require native validation; reference OpenDRIVE signals do not prove rendered native devices.','Summary duration/epsilon is not in exact law; retain raw cessation samples and do not adopt a legal minimum duration.']
 sweeps=[]
 if judgment:
  sweeps=[dict(sweep_id=aid+'__unresolved_judgment',target_law_id=law,judgment_refs=[dict(phrase=('immediate hazard' if law.endswith('253') else 'with safety' if law.endswith('223-1b') else 'sufficient space'),note='Exact full residue retained in template')],status='incomplete',mode='one_dimensional',missing_inputs=gaps,rationale='No legal surrogate or unsupported physical range is selected',variable_assignments=variables,recording_description=rec)]
 config=dict(assignment_id=aid,cell_id=d['cell_id'],actor=d['actor'],law_id=law,supported_case_ids=[x['case_id'] for x in cases],default_case_id=cases[1]['case_id'],mechanism=mechanism,path=path,max_ticks=600,required_atoms=atoms,recording_description=rec,cameras=[dict(x=-8,z=5,pitch=-18,width=1920,height=1080),dict(x=-5,z=2,pitch=-5,width=1280,height=720),dict(x=1,z=2,pitch=-10,width=1280,height=720),dict(x=-2,z=12,pitch=-75,width=1280,height=720)],runtime_gaps=gaps,baseline_selected=False)
 dump(w/'config.json',config);(w/'runner.py').write_text(runner);(w/'runner.py').chmod(0o755);(w/'road-template.xodr').write_bytes((R/'examples/intersection/native/scene-stop257-v1.xodr').read_bytes());(w/'tests').mkdir(exist_ok=True);(w/'tests/test_package.py').write_text(tests)
 dump(w/'proposals/cases.json',dict(cell_id=d['cell_id'],actor=d['actor'],status='draft',cases=cases,sweep_specs=sweeps))
 template=dict(template_id=law+'@'+d['actor'],law_id=law,actor=d['actor'],quote=d['law']['text'],structure=dict(law_id=law,activation=dict(condition='; '.join(summary['activation_conditions']),numeric_conditions=[]),obligation=dict(description=d['law']['text'],type='must',numeric_conditions=[]),exceptions=[dict(trigger=x,effect=x,replacement_obligation=x,source_clause=d['law']['text'][d['law']['text'].find('but such driver'):]) for x in summary['exceptions']],timing=dict(description=summary['timing_requirements'],numeric_conditions=[]),judgment_calls_needed=[dict(phrase=x,note='Unresolved supplied summary residue; no standard adopted') for x in summary['residue']]),parameter_refs=[dict(name=k,kind=v['kind'],range_or_domain='draft physical capability configuration') for k,v in variables.items()])
 dump(w/'proposals/template.json',template)
 dump(w/'proposals/bindings.json',dict(cell_id=d['cell_id'],actor=d['actor'],status='draft',established_contexts=[],law_refs=[],context_refs=[dict(template_id=template['template_id'],missing_guards=d['witness']['required_context'])],fixed_parameters=[dict(name='cell',value=d['cell'],rationale='Supplied exact cell')],variable_parameters=[dict(name=k,kind=v['kind'],range_or_domain='draft',used_by_laws=[law]) for k,v in variables.items()]))
 sources=['inputs/'+aid+'/assignment.json','runtime/stage-contracts.json','runtime/target-environment.json','runtime/python/pipeline_capture.py','examples/intersection/native/scene-stop257-v1.xodr']
 uncertainty=['CARLA unavailable; no physical observations or installed inventory claimed.','Native Python 3.8 dependency imports/client-server compatibility remain unverified.','Controller maneuver completion and camera framing await original-run measurements.']+gaps
 plan=dict(assignment_id=aid,cell_id=d['cell_id'],actor=d['actor'],law_id=law,cases=cases,comparisons=[dict(case_ids=[x['case_id'] for x in cases[1:]],deliberate_differences=['commanded_approach_speed'],fixed_conditions=['map','route','controller implementation','cameras','authored context'],purpose='Capability speed comparison; target legal branches remain pending')],observations=[dict(name=x,mandatory=True) for x in atoms],sources=[dict(path=p,sha256=hashlib.sha256((R/p).read_bytes()).hexdigest()) for p in sources],existing_evidence=d['existing_evidence'],runtime_uncertainties=uncertainty)
 dump(w/'case-plan.json',plan)
 construction=dict(cell_id=d['cell_id'],actor=d['actor'],case_id=cases[1]['case_id'],status='draft',files=[dict(path=p,content=(w/p).read_text()) for p in ['runner.py','config.json','road-template.xodr']],entrypoint='runner.py',mechanisms=['Authored OpenDRIVE builder removes unrelated devices','Observed-state heading and speed feedback; no teleports','Four attached original RGB cameras and tick-neutral PipelineCapture'],measurement_plan=dict(required_atoms=atoms,gaps=gaps),recording_description=rec,static_checks=['stdlib --check map/case/route checks','unittest speed/heading/saturation checks'],termination_rules=['signal','route end within engineering 2m','600 ticks','runtime error; restore settings and owned actors'])
 dump(w/'construction.json',construction)
 for case in cases[2:]:
  proposal=copy.deepcopy(construction);proposal['case_id']=case['case_id'];dump(w/('constructions/'+case['case_id']+'.json'),proposal)
 dump(w/'update-acknowledgements.json',dict(applied_update=2,acknowledgements=[dict(version=2,action='continue',status='applied',note='Fresh six-step executable implementation, no prior planning inherited')]))
 (w/'HANDOFF.md').write_text('# Partial executable preparation\n\nExact law, cell, witness, required observations, timing, exceptions and existing evidence were read from assignment.json. Draft templates/bindings are generated from those supplied sources. No observations are fabricated.\n\nThe runner implements an authored-road builder, physical feedback controller, four RGB cameras, original-frame PipelineCapture, trace and frame maps, signal cleanup and settings restoration. Run `python3.11 runner.py --check`; live CLI is `runner.py --output-dir PATH --host HOST --port PORT --case-id ID`. Baseline stays unselected. Additional canonical proposal: `constructions/'+cases[2]['case_id']+'.json`. Linked implementation files are identical.\n\nThese are physical capability probes, not completed statutory comparisons. All target-law gaps remain explicit in result.reason and config.runtime_gaps; status is partial.\n\n'+ '\n'.join('- '+x for x in uncertainty)+'\n\nFinalization: retain full original recording; validate governed native geometry and every mandatory per-atom stream; derive law-specific target checks with observed physical cause, then freeze range/duration using measured feasibility without selecting legal judgments. Interior judgment sweeps cannot be finalized from these capability probes. Repair at the same frozen target; do not retry unchanged recordings. Project exact summary recording definitions from raw samples, recompute window/statistic values, inspect all four views and emitted indicators, encode synchronized review videos and preserve raw PNGs, frame maps and hashes before downstream adoption. No legal verdict or physical acceptance is claimed.\n')
 logs=[]
 for name,cmd in [('check',['python3.11',str(w.relative_to(R)/'runner.py'),'--check']),('unit',['python3.11','-m','unittest','discover','-s',str(w.relative_to(R)/'tests')])]:
  p=subprocess.run(cmd,cwd=R,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);log=w/('logs/'+name+'.log');log.parent.mkdir(exist_ok=True);log.write_text(p.stdout);logs.append(dict(command=' '.join(cmd),exit_code=p.returncode,log=str(log.relative_to(w)),sha256=hashlib.sha256(log.read_bytes()).hexdigest()))
 dump(w/'result.json',dict(assignment_id=aid,input_sha256=hashlib.sha256((R/'inputs'/aid/'assignment.json').read_bytes()).hexdigest(),status='partial',reason=' '.join(gaps),applied_update=2,tests=logs,runtime_uncertainties=uncertainty))
 print(aid,[(x['exit_code']) for x in logs])
