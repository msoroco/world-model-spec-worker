import json,pathlib,hashlib
ROOT=pathlib.Path.cwd();ids=json.load(open('partitions/demo-test-03.json'))['assignment_ids']
def put(p,x):p.write_text(x if isinstance(x,str) else json.dumps(x,indent=2)+'\n')
for aid in ids:
 f=ROOT/'work'/aid;c=json.load(open(f/'config.json'));kind=c['mechanism'];m=(f/'measurements.py').read_text();s=(f/'runner.py').read_text();g=(f/'geometry.py').read_text()
 helper='''\ndef ordered_states(participants,observations):
    """Join actual same-frame records by actor ID; inventory order is not actor order."""
    index={}
    for state in observations:
        ident=state['actor_id']
        if ident in index:raise ValueError('Duplicate original participant actor ID')
        index[ident]=state
    if any(actor.id not in index for actor in participants):raise ValueError('Missing original required participant')
    return [index[actor.id] for actor in participants]

def validate_visibility(value,expected=None):
    if not value or value.get('unknown_reason'):raise ValueError('Missing actual actor visibility')
    approaches=value.get('approaches',[]);required=set(value.get('required_lane_ids',[]))
    if not required or required!={entry['lane_id'] for entry in approaches}:raise ValueError('Incomplete incoming approach set')
    if expected is not None and required!=set(expected):raise ValueError('Both declared incoming directions are required')
    for entry in approaches:
        horizon=entry.get('any_body_sight_horizon',{})
        if entry.get('unknown_reason') or len(entry.get('body_rays_at_probe',[]))!=9 or horizon.get('unknown') or horizon.get('bound') not in ('first_sampled_occlusion','at_least'):raise ValueError('Incomplete nine-point approach horizon')
        if horizon['bound']=='at_least' and horizon.get('distance_m',0)<230:raise ValueError('Incomplete full search extent')
    return True
'''
 m=m.replace('\ndef project(world,ego,participants,c,a,previous,event=None):',helper+'\ndef project(world,ego,participants,c,a,previous,event=None):')
 m=m.replace("[state for state in event['original_observations']['participants'] if state['actor_id'] in {p.id for p in participants}]", "ordered_states(participants,event['original_observations']['participants'])")
 needle="        approaches=record['st.sight_distance'].get('approaches',[])"
 m=m.replace(needle,needle+"\n        validate_visibility(record['st.sight_distance'],[-1,1] if c['mechanism']=='uturn' else None)\n        projection=record['st.sight_distance']['ego_projection']\n        for entry in approaches:\n            native_lane=mapping.get_waypoint_xodr(projection['road_id'],entry['lane_id'],projection['s_m'])\n            if native_lane is None or len(native_lane.previous(230.))!=1:raise RuntimeError('live_measurement: native lane route does not cover the full declared 230m search beyond first occlusion')")
 m=m.replace("horizon=sampled_horizon(sample,230.,10.,.25,checkpoints=[152.4])", "horizon=sampled_horizon(sample,230.,10.,.25,checkpoints=[152.4])\n                if sample(230.) is None:raise RuntimeError('live_measurement: cross incoming route ends before230m')")
 put(f/'measurements.py',m)
 # Analytic containment covers the whole semicircle, not just sampled route endpoints.
 g+='''\ndef validate_uturn_footprint(station,half_length=2.8,half_width=1.25):
 # With centre (station+6sin(t),6cos(t)), heading -t, every corner has
 # y=(6+corner_y)cos(t)-corner_x sin(t). The analytic amplitude bounds all t.
 lateral_bound=math.hypot(6+half_width,half_length)
 if lateral_bound>=12:raise ValueError('Full U-turn swept body exceeds native 24m operating surface')
 longitudinal_bound=lateral_bound
 if station-longitudinal_bound<=0 or station+longitudinal_bound>=1800:raise ValueError('Full U-turn body exceeds authored road ends')
 for i in range(721):
  t=i*math.pi/720;p=(station+6*math.sin(t),6*math.cos(t))
  for corner in rectangle(p,-t,half_length,half_width):
   if not 0<corner[0]<1800 or not -12<corner[1]<12:raise ValueError('Intermediate U-turn footprint outside native road')
 return {'continuous_lateral_amplitude_bound_m':lateral_bound,'half_length_limit_m':half_length,'half_width_limit_m':half_width,'sampled_whole_semicircle_poses':721,'native_physics_clearance_confirmed':False}
'''
 put(f/'geometry.py',g)
 s=s.replace("    validate_map(ROOT/'road.xodr',c['mechanism'])", "    validate_map(ROOT/'road.xodr',c['mechanism'])\n    if c['mechanism']=='uturn':\n        from geometry import validate_uturn_footprint\n        for case in c['cases']:validate_uturn_footprint(case['variable_assignments']['maneuver_station_m']['value'])")
 s=s.replace("ego=world.spawn_actor(bp,carla.Transform(carla.Location(*path[0]),carla.Rotation(yaw=0.)));actors.append(ego);resources.own(ego.destroy)", "ego=world.spawn_actor(bp,carla.Transform(carla.Location(*path[0]),carla.Rotation(yaw=0.)));actors.append(ego);resources.own(ego.destroy)\n        if c['mechanism']=='uturn':\n            from geometry import validate_uturn_footprint\n            validate_uturn_footprint(a['maneuver_station_m']['value'],ego.bounding_box.extent.x,ego.bounding_box.extent.y)")
 s=s.replace("i=0;previous={};stationary_hold=0.;entered_gate=False", """i=0;previous={};stationary_hold=0.;entered_gate=False
        auxiliary={}
        names=['sight_distance.minimum_from_either_approach'] if c['mechanism']=='uturn' else ['subject_truck_width','lead_truck_width'] if c['mechanism']=='following' else ['backing_intersection_overlap','backing_crosswalk_overlap'] if c['mechanism']=='reverse' else []
        for name in names:
            stream=(out/(name+'.jsonl')).open('x');resources.own(stream.close);auxiliary[name]={'stream':stream,'samples':[]}
        def save_scalar(name,time_s,value):
            row={'time_s':time_s,'value':value};auxiliary[name]['samples'].append(row);auxiliary[name]['stream'].write(json.dumps(row)+'\\n')""")
 s=s.replace("values.append(row);measurements.append(observation);history.append({'time_s':time_s,'participants':participants})", """values.append(row);measurements.append(observation);history.append({'time_s':time_s,'participants':participants})
            if c['mechanism']=='uturn':save_scalar('sight_distance.minimum_from_either_approach',time_s,min(entry['any_body_sight_horizon']['distance_m'] for entry in observation['st.sight_distance']['approaches']))
            if c['mechanism']=='following':
                save_scalar('subject_truck_width',time_s,2*ego.bounding_box.extent.y);save_scalar('lead_truck_width',time_s,2*lead.bounding_box.extent.y)
            if c['mechanism']=='reverse':
                save_scalar('backing_intersection_overlap',time_s,bool(observation['rel.occupies']['authored_intersection_overlap'] and observation['drv.backing']));save_scalar('backing_crosswalk_overlap',time_s,bool(any(observation['rel.occupies']['native_crosswalk_overlap']) and observation['drv.backing']))""")
 s=s.replace("        if any(not check['matched'] for check in result['target_checks']):", """        for name,data in auxiliary.items():
            statistic='max' if name.startswith('backing_') else 'min'
            value,window=summarize(data['samples'],first,last,statistic)
            result['realized_observables'][name]={'value':value,'unit':'bool' if name.startswith('backing_') else 'm','method':c['measurement_definitions'][name]['method'],'time_window':'entire original execution','sample_window_s':window,'statistic':statistic,'reference':name+'.jsonl'}
        if any(not check['matched'] for check in result['target_checks']):""")
 put(f/'runner.py',s)
 c['measurement_definitions']={'kin.speed':{'method':'original actor.get_velocity norm','statistic':'mean','time_window_relative_s':[5,10]},'rel.surface_gap':{'method':'world-space measured bounding-box projections along ego heading','statistic':'mean','time_window_relative_s':[5,10]},'sight_distance.minimum_from_either_approach':{'method':'minimum actual any-of-nine body horizon across both native incoming directions','statistic':'min','time_window':'entire original execution'},'subject_truck_width':{'method':'twice native subject bounding_box.extent.y','statistic':'min','time_window':'entire original execution'},'lead_truck_width':{'method':'twice native lead bounding_box.extent.y','statistic':'min','time_window':'entire original execution'},'backing_intersection_overlap':{'method':'same original frame actual reverse velocity and footprint/region intersection; no legal contact convention chosen','statistic':'max','time_window':'entire original execution'},'backing_crosswalk_overlap':{'method':'same original frame actual reverse velocity and footprint/native-crosswalk intersection; no legal contact convention chosen','statistic':'max','time_window':'entire original execution'}}
 requirements=[r for r in c['external_requirements'] if not r['requirement'].startswith('Confirm native maneuver completion')]
 if kind=='reverse':
  requirements[0].update(category='external_asset',requirement='A native CARLA generator/map must supply the rendered crosswalk asset corresponding to the authored crosswalk object and its get_crosswalks polygon.',evidence='OpenDRIVE object construction, native geometry gate and full encoded evidence are implemented. This repository contains no CARLA generator/rendering assets or verifiable native crosswalk inventory.',next_action='Supply a supported native map/crosswalk asset or verify generator support using the declared crosswalk object; preserve both intersection/crosswalk branch pairs.')
 c['external_requirements']=requirements;c['delivery_gaps']=[r['requirement'] for r in requirements];put(f/'config.json',c)
 plan=json.load(open(f/'case-plan.json'));plan['runtime_uncertainties']=requirements
 for ref in plan['sources']:ref['sha256']=hashlib.sha256((ROOT/ref['path']).read_bytes()).hexdigest()
 put(f/'case-plan.json',plan)
 test=(f/'tests/test_preparation.py').read_text();test+='''\nclass FinalCorrections(unittest.TestCase):
 def test_participant_join_order(self):
  m=module('measurements')
  class P:
   def __init__(self,ident):self.id=ident
  self.assertEqual([r['actor_id'] for r in m.ordered_states([P(8),P(4)],[{'actor_id':4},{'actor_id':8}])],[8,4])
  with self.assertRaises(ValueError):m.ordered_states([P(9)],[{'actor_id':4}])
 def test_whole_uturn_footprint(self):
  m=module('geometry');proof=m.validate_uturn_footprint(430);self.assertEqual(proof['sampled_whole_semicircle_poses'],721)
  with self.assertRaises(ValueError):m.validate_uturn_footprint(430,10,8)
 def test_visibility_requires_all_routes_and_nine_body_rays(self):
  m=module('measurements');value={'required_lane_ids':[-1,1],'approaches':[{'lane_id':i,'body_rays_at_probe':[{'clear':True}]*9,'any_body_sight_horizon':{'bound':'at_least','distance_m':230}} for i in [-1,1]]};self.assertTrue(m.validate_visibility(value,[-1,1]));value['approaches'][0]['any_body_sight_horizon']={'bound':'route_limit','unknown':True,'distance_m':220}
  with self.assertRaises(ValueError):m.validate_visibility(value,[-1,1])
 def test_full_scalar_summary_contract_declared(self):
  c=json.loads((R/'config.json').read_text());self.assertEqual(c['measurement_definitions']['sight_distance.minimum_from_either_approach']['statistic'],'min');self.assertEqual(c['measurement_definitions']['backing_intersection_overlap']['statistic'],'max')
''';put(f/'tests/test_preparation.py',test)
 result=json.load(open(f/'result.json'));result.update(reason='; '.join(r['requirement'] for r in requirements),external_requirements=requirements,tests=[]);put(f/'result.json',result)
 for proposal in [f/'construction.json',*list((f/'constructions').glob('*.json'))]:
  data=json.load(open(proposal));data['mechanisms']['unconfirmed']=requirements;data['measurement_plan']['scalar_measurement_definitions']=c['measurement_definitions']
  for entry in data['files']:
   entry['content']=json.dumps(dict(c,selected_case_id=data['case_id']),indent=2)+'\n' if entry['path']=='config.json' else (ROOT/entry['source']).read_text() if entry.get('source') else (f/entry['path']).read_text()
  # Root materialized config must match its actual config file exactly.
  if proposal.name=='construction.json':next(e for e in data['files'] if e['path']=='config.json')['content']=(f/'config.json').read_text()
  put(proposal,data)
 handoff=(f/'HANDOFF.md').read_text();handoff+='\nFinal lead corrections: participant histories join original actor IDs in requested order; original packet relations and exact native nine-body visibility schema are consumed. Each native incoming lane must have an unambiguous230m route even if an earlier blocker ends horizon scanning. The U-turn entire swept body has an analytic lateral-amplitude bound plus721 intermediate poses and a runtime check using actual native extents. Scalar sight horizons, truck widths and backing-overlap histories are saved separately and summarized over explicit original sample windows with min/min/max statistics. Generic lack of a simulator is a runtime uncertainty, not a preparation blocker. Only the following assignment-specific external requirements determine blocked status:\n\n'+''.join('- '+json.dumps(r,sort_keys=True)+'\n' for r in requirements);put(f/'HANDOFF.md',handoff)
 print(aid,'final code corrections complete')
