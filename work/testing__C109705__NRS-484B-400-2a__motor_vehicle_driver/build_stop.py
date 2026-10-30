import importlib.util,json,pathlib
P=pathlib.Path(__file__).with_name('package_builder.py');s=importlib.util.spec_from_file_location('b',P);b=importlib.util.module_from_spec(s);s.loader.exec_module(b);ROOT=b.ROOT
aid='testing__C331230__NRS-484A-450-2__motor_vehicle_driver';a=json.loads((ROOT/'inputs'/aid/'assignment.json').read_text());seed=ROOT/'references/v6-capability'/aid;run=(seed/'runner.py').read_text();analysis=(seed/'analyze.py').read_text()
mark=(ROOT/'references/accepted-sources/C111325/stop257_markings_v2.py').read_text();mark=mark[:mark.index('def spawn')]+'''def spawn(carla,world,cfg):
 actors=[]
 bp=world.get_blueprint_library().find('static.prop.mesh');bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
 mode=cfg['stop_reference']
 if mode=='marked_crosswalk':xs=[-13+i*.35 for i in range(9)]
 elif mode=='stop_line':xs=[-11]
 else:xs=[]
 for x in xs:
  for i in range(20):
   bp.set_attribute('role_name','statutory_'+mode+'_tile')
   actor=world.spawn_actor(bp,carla.Transform(carla.Location(x=x-CENTER[0],y=.175+.35*i,z=.002-EXTENT[2]*SCALE-CENTER[2])))
   actor.set_simulate_physics(False);actor.set_collisions(False);actors.append(actor)
 return actors

def observe(actors):
 return [{'actor_id':a.id,'body_vertices_m':[[v.x,v.y,v.z] for v in a.bounding_box.get_world_vertices(a.get_transform())]} for a in actors]
'''
run=run.replace('markings=spawn_markings(carla,world,False)','markings=spawn_markings(carla,world,cfg)')
start=run.index('  geometry={');end=run.index("  (out/'crosswalk_geometry.json')",start)
run=run[:start]+'''  mode=cfg['stop_reference'];boundary=-13 if mode=='marked_crosswalk' else -10 if mode=='unmarked_crosswalk' else -11 if mode=='stop_line' else -7.5
  if tiles:boundary=min(v[0] for v in vertices)
  sight=[]
  if mode=='nearest_sight':
   for i in range(70):
    x=-25+i*.25;eye=carla.Location(x=x,y=1.75,z=1.5);rays=[]
    for target in [carla.Location(x=1.75,y=80,z=1.5),carla.Location(x=-1.75,y=-80,z=1.5)]:
     hits=[{'location_m':[h.location.x,h.location.y,h.location.z],'label':str(h.label)} for h in world.cast_ray(eye,target)]
     rays.append({'target_m':[target.x,target.y,target.z],'hits':hits,'clear':not hits})
    sight.append({'candidate_eye_m':[eye.x,eye.y,eye.z],'rays':rays})
   clear=[p for p in sight if all(r['clear'] for r in p['rays'])]
   if not clear:raise ValueError('No sampled visible stopping reference before intersection')
   boundary=max(p['candidate_eye_m'][0] for p in clear)
  (out/'sight_samples.json').write_text(json.dumps({'samples':sight,'resolution_m':.25,'scope':'finite collision rays; no continuous nearest point or optical visibility proof'})+'\\n')
  geometry={'source':'Native physical markings and stop-sign readback; unmarked crosswalk from authored sidewalk prolongations; finite original ray scan',
   'crosswalk_upstream_x_m':boundary,'crosswalk_downstream_x_m':boundary+3 if 'crosswalk' in mode else boundary,
   'crosswalk_physical_tile_count':len(tiles),'physical_marking_inventory':tiles,
   'stop_sign_landmarks':[{'id':str(l.id),'road_id':l.road_id,'type':l.type} for l in mapping.get_all_landmarks() if str(l.type)=='206'],
   'governed_approach_road_id':1,'branch':mode,'stopline_also_present':mode=='stop_line',
   'unmarked_sidewalk_prolongations_m':{'upstream_x':-10,'downstream_x':-7} if mode=='unmarked_crosswalk' else {},
   'public_highway_designation':'synthetic authored assumption; factual status unverified'}
''' +run[end:]
run=run.replace("vertices=[v for tile in tiles for v in tile['body_vertices_m']]", "vertices=[v for tile in tiles for v in tile['body_vertices_m']]")
run=run.replace("if not released:", "if not released and not cfg.get('rolling_probe',False):")
# The diagnostic slowdown epsilon remains solely a controller setting; result exposes full sampled velocity.
analysis=analysis.replace('def finalize(root,output):', '''def nearest_sight_samples(root):
 data=json.loads(required(root,'sight_samples.json').read_text())
 return {'samples':data['samples'],'resolution_m':data['resolution_m'],'scope':data['scope']}

def finalize(root,output):''')
analysis=analysis.replace("'selected_crosswalk_and_stop_control':", "'stopping_sight_scan':{'method':'nearest_sight_samples','value':nearest_sight_samples(root),'sources':{'sight_samples.json':sha('sight_samples.json')}},\n  'crosswalk_stop_context':")
# preserve distinct context key actually used by seed
print([line for line in analysis.splitlines() if "'method':" in line][:4])
def box(x):return [[x+dx,1.75+dy,z] for z in (0,1.5) for dx,dy in [(-2,-.8),(-2,.8),(2,.8),(2,-.8)]]
cases=[];comparisons=[]
for mode in ['marked_crosswalk','unmarked_crosswalk','stop_line','nearest_sight']:
 for roll in [False,True]:
  name=mode+('_rolling' if roll else '_halt');rows=[];bound=-13 if mode=='marked_crosswalk' else -10 if mode=='unmarked_crosswalk' else -11 if mode=='stop_line' else -7.75
  for i,t in enumerate([.05000000074505806,.10000000149011612,.15000000223517418]):rows.append(dict(frame=21714+i,time_s=t,body_vertices_m=box(bound-4+i*.25),speed_mps=5 if roll else 0,dwell_ticks=0 if roll else i,released=False))
  geometry=dict(source='synthetic diagnostic hierarchy geometry',branch=mode,crosswalk_physical_tile_count=180 if mode=='marked_crosswalk' else 0,crosswalk_upstream_x_m=bound,crosswalk_downstream_x_m=bound+3,stop_sign_landmarks=[dict(id='206',road_id=1,type='206')],governed_approach_road_id=1,stopline_also_present=mode=='stop_line',public_highway_designation='authored diagnostic assumption; no factual highway proof')
  sight=dict(samples=[dict(candidate_eye_m=[-8+i*.25,1.75,1.5],rays=[dict(target_m=[1.75,80,1.5],hits=[],clear=True)]) for i in range(2)] if mode=='nearest_sight' else [],resolution_m=.25,scope='diagnostic finite rays, not original pixels or continuous statutory nearest point')
  cases.append(dict(name=name,rationale='Crosswalk-first statutory stopping hierarchy; compare complete halt and rolling movement with same reference geometry.',config=dict(stop_reference=mode,rolling_probe=roll),fixture={'crosswalk_geometry.json':geometry,'stop_history.jsonl':''.join(json.dumps(r)+'\n' for r in rows),'sight_samples.json':sight}))
 comparisons.append(dict(comparison_id=mode+'_cessation',cases=[mode+'_halt',mode+'_rolling'],fixed_conditions=['Same stop-sign intersection and stopping-reference hierarchy','Same marking presence/absence, route, duration and cameras'],deliberate_differences=['Stop controller enabled versus rolling approach; preserve raw velocity samples without legal stop epsilon']))
topics=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())['laws'][a['law_id']]['topics']
# Keys copied from the exact seed output.
ms=[dict(output_key='pre_crosswalk_body_front_and_speed',method='stop_before_crosswalk',kind='measured',value_type='object',inputs=['crosswalk_geometry.json','stop_history.jsonl']),dict(output_key='selected_crosswalk_and_stop_control',method='crosswalk_stop_context',kind='sourced_context',value_type='object',inputs=['crosswalk_geometry.json']),dict(output_key='stopping_sight_scan',method='nearest_sight_samples',kind='measured',value_type='object',inputs=['sight_samples.json'])]
import re;print(re.findall(r"'([^']+)':\{'method'",analysis))
reqs=[a['law']['text'],'Crosswalk first, marked line only if no crosswalk, nearest sight point only if neither; marked and sidewalk-prolongation crosswalk definitions.','Nearest-point sight evidence retains driver-view collision-ray samples and scan resolution; do not infer continuous optical view.']
spec=dict(assignment_id=aid,runner=run,analysis=analysis,extra_files={'crosswalk_markings.py':mark},reference_paths=['references/accepted-sources/C111325/stop257_markings_v2.py'],test='''import unittest,tempfile\nfrom pathlib import Path\nfrom analyze import stop_before_crosswalk\nfrom runner import check\nclass T(unittest.TestCase):\n def test_topology(self):self.assertTrue(check()['stop_approach_connected'])\n def test_missing(self):\n  with tempfile.TemporaryDirectory() as t:\n   with self.assertRaisesRegex(ValueError,'Missing required source: crosswalk_geometry.json'):stop_before_crosswalk(Path(t))\n''',cases=cases,dispositions=[dict(requirement=r,source=a['law']['source'] if i==0 else 'assignment.witness.required_context and DEF-065',evidence_or_gap='Native original body-front/velocity samples and hierarchy geometry; independent legal reference-point and stopping judgment.',measurement=m) for i,(r,m) in enumerate(zip(reqs,ms))],negative=dict(remove=['crosswalk_geometry.json'],error_contains='Missing required source: crosswalk_geometry.json'),measurement_plan='Original full-body front relative to crosswalk, line or finite nearest-sight reference; all velocity samples retained without legal cessation epsilon.',static_checks=['Connected stop approach and stop sign','Physical marking mesh builder and hierarchy presence/absence','All four cameras at 20Hz for 45 seconds'],mechanisms=['Closed-loop physical braking versus rolling controller','Source-hashed physical markings adapted from accepted mesh tiles','Native collision ray driver-view scan for sight fallback'],limitations=['Actual physical stop, continuous nearest sight point, driver viewpoint and pixels require GPU review.','Physical crosswalk/line readback and unmarked sidewalk prolongation alignment require independent verification.'],observation_mapping={},audits=['Verify hierarchy order crosswalk before line before nearest view','Audit complete cessation from raw original velocity and body position; no numerical legal stop criterion','Audit driver-eye ray scan and rendered pixel visibility separately'],comparisons=comparisons,branches=[dict(name=c['comparison_id'],topic_ids=list(topics),cases=c['cases'],comparison_ids=[c['comparison_id']]) for c in comparisons])
# Realize sidewalks whose lateral boundary prolongations define the unmarked crossing.
import xml.etree.ElementTree as ET
for case in spec['cases']:
 if case['config']['stop_reference']=='unmarked_crosswalk':
  tree=ET.fromstring((seed/'scene.xodr').read_text())
  for road in tree.findall('road'):
   if road.get('id') in ('3','4'):
    for side,identity in [('left','3'),('right','-3')]:
     parent=road.find('lanes/laneSection/'+side);lane=ET.SubElement(parent,'lane',id=identity,type='sidewalk',level='false');ET.SubElement(lane,'link');ET.SubElement(lane,'width',sOffset='0',a='3',b='0',c='0',d='0')
  case['scene']=ET.tostring(tree,encoding='unicode')
b.write(ROOT/'work'/aid/'package-spec.json',spec);b.build(spec)
