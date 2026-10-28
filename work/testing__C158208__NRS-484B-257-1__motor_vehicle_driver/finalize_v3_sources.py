"""Finish measured source integration and refresh inline provenance after shared stabilization."""
import json,pathlib,hashlib
ROOT=pathlib.Path.cwd();ids=json.load(open('partitions/demo-test-03.json'))['assignment_ids']
for aid in ids:
 f=ROOT/'work'/aid;c=json.load(open(f/'config.json'));s=(f/'runner.py').read_text();m=(f/'measurements.py').read_text()
 s=s.replace("((3,range(480,490,2)),(21,range(0,20,2)),(4,range(0,200,2)))", "((21,range(2,20,2)),(4,range(0,200,2)))")
 s=s.replace("w=world.get_map().get_waypoint_xodr(3,-1,480.);", "w=world.get_map().get_waypoint_xodr(21,-1,2.);")
 s=s.replace("else 4.\n                if lead_index", "else (3. if entered_gate else 0.)\n                if lead_index")
 s=s.replace("            observation,participants,body=project(world,ego,actors,c,a,previous)\n            row=recording.tick(frame,time_s,observation);values.append(row);measurements.append(observation);history.append({'time_s':time_s,'participants':participants})", """            captured={}
            def measure(row,event):
                observation,participants,body=project(world,ego,actors,c,a,previous,event)
                captured.update(observation=observation,participants=participants,body=body)
                return observation
            row=recording.tick(frame,time_s,measure)
            observation=captured['observation'];participants=captured['participants'];body=captured['body']
            values.append(row);measurements.append(observation);history.append({'time_s':time_s,'participants':participants})""")
 m=m.replace("def project(world,ego,participants,c,a,previous):", "def project(world,ego,participants,c,a,previous,event=None):")
 m=m.replace("states=[actor_state(p) for p in participants];subject=", "states=([state for state in event['original_observations']['participants'] if state['actor_id'] in {p.id for p in participants}] if event else [actor_state(p) for p in participants]);subject=")
 m=m.replace("record['rel.visible']=[visible_relation(world,ego,p) for p in participants if p.id!=ego.id]", "record['rel.visible']=event['original_observations']['relations'] if event else [visible_relation(world,ego,p) for p in participants if p.id!=ego.id]")
 m=m.replace("record['st.sight_distance']=actor_visibility(world,ego,mapping=mapping)", "record['st.sight_distance']=event['visibility'] if event else actor_visibility(world,ego,mapping=mapping)")
 m=m.replace("        approaches=record['st.sight_distance'].get('approaches',[])", """        if not record['st.sight_distance']:raise RuntimeError('Required original visibility packet unavailable')
        approaches=record['st.sight_distance'].get('approaches',[])""")
 m=m.replace("if record['st.sight_distance'].get('unknown_reason') or not approaches or any(x.get('unknown_reason') or x.get('any_body_sight_horizon',{}).get('bound')=='route_limit' for x in approaches):", "if record['st.sight_distance'].get('unknown_reason') or not approaches or set(record['st.sight_distance'].get('required_lane_ids',[]))!={x['lane_id'] for x in approaches} or any(x.get('unknown_reason') or not x.get('any_body_sight_horizon') or x['any_body_sight_horizon'].get('unknown') or x['any_body_sight_horizon'].get('bound')=='route_limit' for x in approaches):")
 m=m.replace("    selected={o['name']:record[o['name']] for o in c['observations']}", """        if c['mechanism']=='yield':
            # Independently retain both incoming cross-road approaches, without calling them ego incoming-lane horizons.
            from carla_sgg.law_evidence import sampled_horizon,ray_evidence
            targets=[t.transform(carla.Location(ego.bounding_box.location))]+list(ego.bounding_box.get_world_vertices(t));cross=[]
            for road in (3,4):
                def sample(distance):
                    station=490-distance if road==3 else distance
                    waypoint=mapping.get_waypoint_xodr(road,-1 if road==3 else 1,station)
                    if waypoint is None:return None
                    eye=waypoint.transform.location+carla.Location(z=1.4)
                    return [ray_evidence(world,ego,eye,p) for p in targets]
                horizon=sampled_horizon(sample,230.,10.,.25,checkpoints=[152.4])
                if horizon.get('bound')=='route_limit' or horizon.get('unknown'):raise RuntimeError('live_measurement: cross-road incoming approach lacks complete 230m nine-body route coverage')
                cross.append({'road_id':road,'lane_id':-1 if road==3 else 1,'distance_origin':'native intersection approach endpoint; actor body targets remain actual original-frame positions','any_body_sight_horizon':horizon,'body_rays_at_152_4m':sample(152.4)})
            record['st.sight_distance']['through_road_incoming_approaches']=cross
    selected={o['name']:record[o['name']] for o in c['observations']}""")
 (f/'runner.py').write_text(s);(f/'measurements.py').write_text(m)
 # Add frozen raw scalar horizon history; it is a measured physical channel separate from the structured full-ray channel.
 # The numeric summaries for the ordinary sight probes remain target checks, not fabricated sweep realizations.
 (f/'recording.py').write_text((ROOT/'work/_shared/recording.py').read_text())
 test=(f/'tests/test_preparation.py').read_text().replace("'recording.tick(frame,time_s,observation)'","'recording.tick(frame,time_s,measure)'")
 (f/'tests/test_preparation.py').write_text(test)
 tests=(f/'tests/test_full_output.py').read_text();tests+='''\nclass AssignmentMandatoryChannels(Contracts):
 def setUp(self):
  super().setUp();config=json.loads((pathlib.Path(__file__).resolve().parents[1]/'config.json').read_text());self.desc=config['cases'][0]['recording_description']
  self.result['recording_evidence']=[]
  for i,channel in enumerate(self.desc['channels']):
   name=channel['name'];reference='mandatory-'+str(i)+'.jsonl';self.put(reference,[dict(time_s=j*.05,value=1) for j in range(2)]);self.result['recording_evidence'].append(dict(name=name,reference=reference))
  (self.root/'context.json').write_text(json.dumps({'authored_test_context':{'fixture':'synthetic software test; not a physical feasibility claim'}}));self.result['recording_evidence'].append(dict(name='authored_test_context',reference='context.json'));self.result['realized_observables']={}
 def test_success_every_assignment_mandatory_channel(self):self.assertTrue(self.validate())
 def test_every_assignment_null_channel_rejected(self):
  for channel in self.desc['channels']:
   evidence=next(e for e in self.result['recording_evidence'] if e['name']==channel['name']);self.put(evidence['reference'],[dict(time_s=j*.05,value=None) for j in range(2)]);self.assertRaises(ValueError,self.validate);self.put(evidence['reference'],[dict(time_s=j*.05,value=1) for j in range(2)])
'''
 # Avoid inheriting tests whose setUp assumptions intentionally differ; retain only generic fixture setup and new assignment tests.
 tests=tests.replace('class AssignmentMandatoryChannels(Contracts):','class AssignmentMandatoryChannels(unittest.TestCase):\n setUpClass=Contracts.__dict__[\'setUpClass\']\n tearDownClass=Contracts.__dict__[\'tearDownClass\']\n put=Contracts.put\n validate=Contracts.validate').replace('  super().setUp();config=', '  Contracts.setUp(self);config=')
 (f/'tests/test_full_output.py').write_text(tests)
 plan=json.load(open(f/'case-plan.json'))
 for ref in plan['sources']:ref['sha256']=hashlib.sha256((ROOT/ref['path']).read_bytes()).hexdigest()
 (f/'case-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 for proposal in [f/'construction.json',*list((f/'constructions').glob('*.json'))]:
  data=json.load(open(proposal))
  for entry in data['files']:
   if entry['path']!='config.json':entry['content']=(ROOT/entry['source']).read_text() if entry.get('source') else (f/entry['path']).read_text()
  proposal.write_text(json.dumps(data,indent=2)+'\n')
 print(aid,'strict packet and channel fixtures integrated')
