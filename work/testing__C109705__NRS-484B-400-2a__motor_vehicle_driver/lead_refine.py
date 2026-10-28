import pathlib,json,copy,math
R=pathlib.Path.cwd(); ids=json.loads((R/'partitions/demo-test-01.json').read_text())['assignment_ids']
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
module='''"""Law-specific physical branch selection and observed geometry; no legal verdict."""
import math

def route(c,case):
    v=case['variable_assignments']; law=c['law_id']
    lateral=v.get('commanded_approach_lateral_m',{}).get('value',1.75)
    destination=v.get('commanded_exit_lateral_m',{}).get('value',1.75)
    if law.endswith(('400-2a','400-2b','253')):
        start=-7; end=-7
        p=[[-80+i,lateral] for i in range(74)]
        # Cubic Bezier preserves approach/exit tangents; whole route remains fixed across speed sweeps.
        a=(-7,lateral);b=(destination-5,lateral);d=(destination,-7);cc=(destination,-2)
        for i in range(1,41):
            t=i/40;u=1-t;p.append([u**3*a[j]+3*u*u*t*b[j]+3*u*t*t*cc[j]+t**3*d[j] for j in range(2)])
        p += [[destination,-7-i] for i in range(1,54)]
        return p
    if law.endswith('223-1b'):
        return [[-80+i,1.75+3.5*(.5-.5*math.cos(math.pi*max(0,min(1,(i-40)/30))))] for i in range(141)]
    return c['path']

def footprint_gap(ego,other):
    a=ego.bounding_box.get_world_vertices(ego.get_transform());b=other.bounding_box.get_world_vertices(other.get_transform())
    # Straight eastbound following only; retain raw vertices for arbitrary-path downstream geometry.
    return min(p.x for p in b)-max(p.x for p in a)

def physical_sample(ego,path,others,world):
    t=ego.get_transform();p=t.location;velocity=ego.get_velocity()
    near=min(math.hypot(p.x-x,p.y-y) for x,y in path)
    return dict(position_m=[p.x,p.y,p.z],heading_deg=t.rotation.yaw,speed_mps=math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2),route_error_m=near,
        body_vertices_m=[[v.x,v.y,v.z] for v in ego.bounding_box.get_world_vertices(t)],
        participants=[dict(actor_id=a.id,position_m=[a.get_location().x,a.get_location().y,a.get_location().z],body_vertices_m=[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]) for a in others],
        gap_m=footprint_gap(ego,others[0]) if others else None,ego_lamp_bits=int(ego.get_light_state()),
        devices=[dict(actor_id=a.id,state=str(a.get_state())) for a in world.get_actors().filter('traffic.traffic_light*')])

def target_checks(case,samples):
    v=case['variable_assignments'];out=[]
    if not samples:return out
    for key,window,coordinate in [('commanded_approach_lateral_m',lambda s:s['position_m'][0]<-10,1),('commanded_exit_lateral_m',lambda s:s['position_m'][1]<-12,0)]:
        if key in v:
            values=[s['position_m'][coordinate] for s in samples if window(s)]
            measured=sum(values)/len(values) if values else None
            out.append(dict(target=key,requested=v[key]['value'],measured=measured,method='mean actual CARLA position in stated approach/exit window',tolerance=.35,matched=measured is not None and abs(measured-v[key]['value'])<=.35,physical_cause_confirmed=None,cause_evidence='physical_samples.jsonl; native roadway verification still required'))
    if 'commanded_gap_m' in v:
        vals=[s['gap_m'] for s in samples if s['gap_m'] is not None];value=sum(vals[-100:])/len(vals[-100:]) if vals else None
        out.append(dict(target='commanded_gap_m',requested=v['commanded_gap_m']['value'],measured=value,method='mean final up-to-100 straight-road footprint gaps',tolerance=2,matched=value is not None and abs(value-v['commanded_gap_m']['value'])<=2,physical_cause_confirmed=bool(vals),cause_evidence='physical_samples.jsonl actual body vertices'))
    if 'commanded_halt' in v:
        values=[s['speed_mps'] for s in samples if -20<s['position_m'][0]<-8];value=min(values) if values else None
        out.append(dict(target='commanded_halt',requested=v['commanded_halt']['value'],measured=value,method='minimum observed speed before intersection; full raw history retained, no legal duration invented',tolerance=None,matched=None,physical_cause_confirmed=None,cause_evidence='physical_samples.jsonl and native sign/crosswalk hierarchy audit pending'))
    return out
'''
for aid in ids:
 w=R/'work'/aid;c=json.loads((w/'config.json').read_text());p=json.loads((w/'proposals/cases.json').read_text());law=c['law_id'];original=json.loads((R/'inputs'/aid/'assignment.json').read_text());base=copy.deepcopy(p['cases'][0]);cases=[base]
 if law.endswith('400-2a'): key='commanded_approach_lateral_m';values=[1.75,5.25];names=['inner_approach','outer_approach'];types=['compliant_attempt','violating_attempt']
 elif law.endswith('400-2b'):key='commanded_exit_lateral_m';values=[1.75,-1.75];names=['right_exit','left_exit'];types=['compliant_attempt','violating_attempt']
 elif law.endswith('223-1b'):key='commanded_signal';values=[True,False];names=['signal','no_signal'];types=['boundary_probe']*2;c['mechanism']='lane_change'
 elif law.endswith('450-2'):key='commanded_halt';values=[True,False];names=['halt','no_halt'];types=['compliant_attempt','violating_attempt']
 elif law.endswith('127-3'):key='commanded_gap_m';values=[15,30,45];names=['gap_15','gap_30','gap_45'];types=['boundary_probe']*3
 else:key='commanded_yield';values=[True,False];names=['yield','no_yield'];types=['boundary_probe']*2
 unit='m' if key.endswith(('_m',)) else 'boolean'
 for name,value,typ in zip(names,values,types):
  case=copy.deepcopy(base);case.update(case_id=aid+'__'+name,target_law_id=law,target_type=typ,rationale='Plain statutory branch; actual outcome requires original measured evidence' if typ!='boundary_probe' else 'Physical branch probe with judgments unresolved; no anticipated compliance label',paired_probe_id=aid+'__comparison',deliberate_differences=[key],probe=dict(primary_variable=key,comparison_or_standard='exact target law clause; no judgment cutoff',target_value_or_branch=value));case['variable_assignments'][key]=dict(kind='controller',value=value,unit=unit);cases.append(case)
 p['cases']=cases
 # Freeze all branches using the same implementation; additional proposal carries only selected case ID.
 c.update(supported_case_ids=[x['case_id'] for x in cases],default_case_id=cases[1]['case_id'])
 if law.endswith('127-3'):
  c['path']=[[-250+i,1.75] for i in range(501)];c['max_ticks']=1600
  base['variable_assignments']['authored_context']['value'].update(caravan_membership='explicit synthetic assumption for ego and lead, not inferred from motion',outside_business_district='explicit synthetic assumption; no scene-derived legal classification')
 for case in cases:
  case['variable_assignments']['authored_context']=copy.deepcopy(base['variable_assignments']['authored_context'])
 # Keep every proposed judgment incomplete until physically tested ranges can be frozen.
 for s in p['sweep_specs']:
  s['judgment_refs']=[dict(phrase=x['phrase'],note=x['note']) for x in json.loads((w/'proposals/template.json').read_text())['structure']['judgment_calls_needed']]
 oldg=c['runtime_gaps']; c['runtime_gaps']=[x for x in oldg if not any(t in x for t in ('comparison branches require','gap controller remain','signal timing'))]
 c['runtime_gaps']+=['Law-specific controller branches and raw geometry are implemented; map/device governance, full mandatory atom projections and physical feasibility remain unconfirmed.']
 if law.endswith('223-1b'):c['runtime_gaps']+=['One-way lane topology and signposted designation are not yet authored in the inherited two-way map; emitted indicator visibility and safety judgment remain unverified.']
 write(w/'config.json',c);write(w/'proposals/cases.json',p);(w/'scenario.py').write_text(module)
 run=(w/'runner.py').read_text().replace('def speed(v):','from scenario import route,physical_sample,target_checks,footprint_gap\n\ndef speed(v):')
 run=run.replace("assert not any(x.get('expected_label') for x in p['sweep_specs'])","assert not any(x.get('expected_label') for x in p['sweep_specs'])\n    for case in p['cases']:\n        path=route(c,case);assert all(math.dist(a,b)<4 for a,b in zip(path,path[1:]))")
 run=run.replace("case=cases[args.case_id or c['default_case_id']]","case=cases[args.case_id or c['default_case_id']]\n    c['path']=route(c,case)")
 run=run.replace('streams=[]','streams=[];samples=[];others=[];halt_start=None')
 run=run.replace("sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))","""if c['law_id'].endswith(('127-3','253')):
            pos=ego.get_location();op=carla.Transform(carla.Location(x=pos.x+30 if c['law_id'].endswith('127-3') else 60,y=pos.y if c['law_id'].endswith('127-3') else -1.75,z=.5),carla.Rotation(yaw=0 if c['law_id'].endswith('127-3') else 180))
            other=world.spawn_actor(bp,op);actors.append(other);others.append(other)
        if case['variable_assignments'].get('commanded_signal',{}).get('value',False):ego.set_light_state(carla.VehicleLightState.LeftBlinker)
        sys.path.insert(0,str(ROOT.parents[1]/'runtime/python'))""")
 run=run.replace("result['behavior_attempted']=True","physical=(out/'physical_samples.jsonl').open('x');streams.append(physical)\n        result['behavior_attempted']=True")
 old="if c['mechanism']=='stop' and case['variable_assignments'].get('commanded_halt',{}).get('value') and t.location.x>-25 and t.location.x<-10:target=min(target,math.sqrt(2*1.5*max(0,-14-t.location.x)))"
 new="""if c['mechanism']=='stop' and case['variable_assignments'].get('commanded_halt',{}).get('value') and halt_start!='released':
                target=min(target,math.sqrt(2*1.5*max(0,-14-t.location.x)))
                if v<.05 and t.location.x>-20:
                    if halt_start is None:halt_start=tick
                    elif tick-halt_start>=40:halt_start='released'
            if others:
                other=others[0];ov=speed(other.get_velocity());ot=5
                if c['law_id'].endswith('127-3'):
                    gap=footprint_gap(ego,other);desired=case['variable_assignments']['commanded_gap_m']['value'];target=max(0,min(8,5+.25*(gap-desired)));ot=5
                elif case['variable_assignments'].get('commanded_yield',{}).get('value') and other.get_location().x>-12 and t.location.x>-20:target=0
                other.apply_control(carla.VehicleControl(throttle=max(0,min(.6,.45*(ot-ov))),brake=max(0,min(1,.45*(ov-ot)))))"""
 run=run.replace(old,new)
 run=run.replace("cap.capture(frame,time_s,extra={'ego_lamp_bits':int(ego.get_light_state())})","cap.capture(frame,time_s,extra={'ego_lamp_bits':int(ego.get_light_state())})\n            sample=physical_sample(ego,c['path'],others,world);sample['time_s']=time_s;samples.append(sample);physical.write(json.dumps(sample)+'\\n')")
 run=run.replace("result['measured_values']={'captured_frames':frames}","result['target_checks']=target_checks(case,samples)\n        result['measured_values']={'captured_frames':frames,'maximum_route_error_m':max((s['route_error_m'] for s in samples),default=None)}")
 # helper imported from package even when loaded by spec in tests.
 run=run.replace('from scenario import',"sys.path.insert(0,str(ROOT))\nfrom scenario import")
 (w/'runner.py').write_text(run)
 plan=json.loads((w/'case-plan.json').read_text());plan.update(cases=cases,comparisons=[dict(case_ids=[x['case_id'] for x in cases[1:]],deliberate_differences=[key],fixed_conditions=['map','camera configurations','physical controller implementation','all other variable assignments'])]);write(w/'case-plan.json',plan)
 result=json.loads((w/'result.json').read_text());result['reason']=' '.join(c['runtime_gaps']);write(w/'result.json',result)
 for old in (w/'constructions').glob('*.json'):old.unlink()
 con=json.loads((w/'construction.json').read_text());con['case_id']=cases[1]['case_id'];con['files']=[dict(path=p,content=(w/p).read_text()) for p in ['runner.py','scenario.py','config.json','road-template.xodr']];con['measurement_plan']['gaps']=c['runtime_gaps'];write(w/'construction.json',con)
 for case in cases[2:]:cc=copy.deepcopy(con);cc['case_id']=case['case_id'];write(w/'constructions'/(case['case_id']+'.json'),cc)
 h=(w/'HANDOFF.md').read_text();h+='\nLead refinement: replaced speed capability comparisons with law-specific '+key+' branches. All linked members use identical files and explicit --case-id selection. Added observed footprint gaps, feedback following, oncoming participant control, approach/exit geometry target checks, halt/release state and actual lamp commands. Additional canonical proposals: '+', '.join('constructions/'+x['case_id']+'.json' for x in cases[2:])+'. Residual partial reasons are authoritative in result.json. Native map geometry and full atom capture remain unconfirmed.\n';(w/'HANDOFF.md').write_text(h)
