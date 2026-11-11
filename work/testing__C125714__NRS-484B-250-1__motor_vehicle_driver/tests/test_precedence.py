import hashlib,importlib.util,io,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parents[1]/'runtime/scenario_pipeline'))
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
measure=load('crossing_precedence');native=load('native_crossing');comparison=load('comparison_audit');geometry=load('median_geometry');spacing=load('median_spacing');capture=load('capture_sources');finalizer=load('finalizer');runner=load('runner');cameras=load('camera_setup');encoder=load('camera_encoder');turns=load('turn_exception_audit');turn_fixture=load('turn_exception_fixture_proof')
route=load('route_control')
site_packet=load('site_packet')
def body(x,y):return [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
class Tests(unittest.TestCase):
    def test_authored_route_steering_and_progress(self):
        points=[[0,0],[10,0],[10,10],[10,20]]
        self.assertIs(route.validate_route(points,[0,0,0,0],[10,0,0,0],'ego'),points)
        steer,index=route.steering_command(8,0,0,points)
        self.assertLess(steer,0)
        self.assertEqual(index,2)
        steer,index=route.steering_command(10,9,90,points,index)
        self.assertEqual(index,3)
        self.assertAlmostEqual(steer,0,places=5)
        with self.assertRaisesRegex(ValueError,'differs from reviewed'):
            route.validate_route([[6,0],[10,0],[10,10]], [0,0,0,0],[10,0,0,0],'ego')
        with self.assertRaisesRegex(ValueError,'near-duplicate'):
            route.validate_route([[0,0],[0.2,0],[10,0],[10,10]], [0,0,0,0],[10,0,0,0],'ego')
        crossing=[[0,0],[10,0],[10,10],[0,10]]
        self.assertEqual(route.validate_route([[-5,5],[5,5],[15,5]],
                                              [-5,5,0,0],[5,5,0,0],
                                              'ego',crossing)[-1],[15,5])
        with self.assertRaisesRegex(ValueError,'ends within crossing'):
            route.validate_route([[-5,5],[5,5],[8,5]],[-5,5,0,0],
                                 [5,5,0,0],'ego',crossing)
        with self.assertRaisesRegex(ValueError,'does not traverse crossing interior'):
            route.validate_route([[-5,-2],[5,-2],[15,-2]],[-5,-2,0,0],
                                 [5,-2,0,0],'ego',crossing)
    def test_device_review_requires_entrance_coverage_and_no_control(self):
        site={'crossing_id':5,'native_map_name':'TownX',
              'ego_highway_id':1,'other_highway_id':2}
        review={'format':'worker-median-device-inventory','crossing_id':5,
                'native_map_name':'TownX','all_entrances_reviewed':True,
                'review_basis':'synthetic entrance coverage fixture',
                'entrances':[{'road_id':11,'lane_id':-1,'highway_id':1},
                             {'road_id':22,'lane_id':-1,'highway_id':2}],
                'devices':[]}
        self.assertEqual(site_packet.verify_device_review(review,site)
                         ['reviewed_entrance_count'],2)
        missing=json.loads(json.dumps(review))
        missing['entrances'].pop()
        with self.assertRaisesRegex(ValueError,'At least two reviewed'):
            site_packet.verify_device_review(missing,site)
        controlled=json.loads(json.dumps(review))
        controlled['devices']=[{'type':'stop','source':'synthetic device',
                                'controls_crossing':True}]
        with self.assertRaisesRegex(ValueError,'Official device controls'):
            site_packet.verify_device_review(controlled,site)
    def test_precedence_controller_holds_until_other_clears(self):
        held,entered=runner.precedence_hold(False,False)
        self.assertTrue(held)
        held,entered=runner.precedence_hold(True,entered)
        self.assertTrue(held)
        held,entered=runner.precedence_hold(False,entered)
        self.assertFalse(held)
        self.assertTrue(entered)
        def actor(points):
            vertices=[NS(x=x,y=y) for x,y in points]
            return NS(bounding_box=NS(get_world_vertices=lambda transform:vertices),
                      get_transform=lambda:object())
        from shapely.geometry import Polygon
        crossing=Polygon([[0,0],[10,0],[10,10],[0,10]])
        self.assertFalse(runner._body_inside(actor(body(-4,5)),crossing))
        self.assertTrue(runner._body_inside(actor(body(5,5)),crossing))
        with self.assertRaisesRegex(ValueError,'Complete finite Native body'):
            runner._body_inside(actor([[0,0],[1,0],[1,1]]),crossing)
    def test_median_spacing_boundary_and_selected_crossing(self):
        crossing=[[0,0],[10,0],[10,10],[0,10]]
        def document(gap):
            return {'format':'worker-median-roadway-geometry','units':'m',
                    'source_description':'synthetic boundary probe',
                    'roadway_polygons_xy_m':[crossing,
                        [[0,10+gap],[10,10+gap],[10,20+gap],[0,20+gap]]]}
        self.assertEqual(spacing.check_roadway_pair(document(9.143),crossing,0)
                         ['boundary_relation'],'below')
        at=spacing.check_roadway_pair(document(9.144),crossing,0)
        self.assertEqual(at['boundary_relation'],'at')
        self.assertTrue(at['separate_roadway_crossings_geometry_candidate'])
        self.assertEqual(spacing.check_roadway_pair(document(9.145),crossing,0)
                         ['boundary_relation'],'above')
        with self.assertRaisesRegex(ValueError,'Selected roadway misses'):
            spacing.check_roadway_pair(document(9.144),crossing,1)
        with self.assertRaisesRegex(ValueError,'spans both'):
            spacing.check_roadway_pair(document(9.144),
                                      [[0,0],[10,0],[10,30],[0,30]],0)
    def fixture(self,root,other_first=True):
        ctx={'native_map_id':'TownX','intersection_id':5,'ego_highway_id':1,'other_highway_id':2,'ego_road_id':11,'other_road_id':22,'crossing_geometry_source':'native-junction','all_entrances_source':'native-road-inventory','official_device_inventory_source':'native-and-camera','median_spacing_source':'native-map','same_statutory_crossing':True,'official_device_controls_crossing':False,'opposite_approach_with_left_turn':False,'intersection_polygon_xy_m':[[0,0],[10,0],[10,10],[0,10]]}
        (root/'junction_context.json').write_text(json.dumps(ctx))
        spots= [((-4,5), (14,5)), ((-4,5),(5,5)),((5,5),(5,5))] if other_first else [((-4,5),(14,5)),((5,5),(14,5)),((5,5),(5,5))]
        rows=[]
        for i,(ego,other) in enumerate(spots):
            rows.append({'frame':100+i,'time_s':i*.05,'ego_vertices_m':body(*ego),'ego':{'intersection_id':5,'road_id':11,'body_vertices_xy_m':body(*ego)},'other':{'intersection_id':5,'road_id':22,'body_vertices_xy_m':body(*other)}})
        frames=[{'video_frame':i,'carla_frame':r['frame'],'time_s':r['time_s']} for i,r in enumerate(rows)]
        (root/'crossing_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
    def test_precedence_and_negative_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,True);r=measure.analyze(root)
            self.assertTrue(r['other_enters_before_ego']);self.assertTrue(r['other_body_inside_at_ego_entry'])
            self.fixture(root,False);self.assertFalse(measure.analyze(root)['other_enters_before_ego'])
    def test_device_exclusion_and_frame_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            ctx=json.loads((root/'junction_context.json').read_text());ctx['official_device_controls_crossing']=True;(root/'junction_context.json').write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,'Official-device'):measure.analyze(root)
            self.fixture(root);frames=[json.loads(x) for x in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
            with self.assertRaisesRegex(ValueError,'frame join'):measure.analyze(root)
            self.fixture(root)
            rows=[json.loads(x) for x in (root/'crossing_history.jsonl').read_text().splitlines()]
            rows[1]['ego_vertices_m']=body(50,50)
            (root/'crossing_history.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in rows))
            with self.assertRaisesRegex(ValueError,'Pinned physical ego body differs'):
                measure.analyze(root)
    def test_native_device_and_spawn_cleanup(self):
        actors=[]
        world=NS(get_actors=lambda:NS(filter=lambda q:actors),try_spawn_actor=lambda bp,tr:NS(destroy=lambda:actors.append('destroyed')))
        native.verify_uncontrolled_crossing(world,5,[(11,-1),(22,-1)])
        device=NS(id=8,get_affected_lane_waypoints=lambda:[NS(road_id=11,lane_id=-1)])
        actors.append(device)
        with self.assertRaisesRegex(ValueError,'Official device'):native.verify_uncontrolled_crossing(world,5,[(11,-1),(22,-1)])
        actors.clear()
        with native.spawn_other(world,'vehicle','transform') as actor:self.assertIsNotNone(actor)
        self.assertEqual(actors,['destroyed'])
    def test_entry_order_comparison_and_fixed_conditions(self):
        with tempfile.TemporaryDirectory() as tmp:
            left,right=Path(tmp)/'left',Path(tmp)/'right'
            left.mkdir();right.mkdir()
            self.fixture(left,True);self.fixture(right,False)
            proof=comparison.audit_entry_order(left,right,3)
            self.assertTrue(proof['software_comparison_passed'])
            self.assertNotEqual(proof['left_other_enters_before_ego'],proof['right_other_enters_before_ego'])
            self.fixture(right,True)
            with self.assertRaisesRegex(ValueError,'ordering difference'):
                comparison.audit_entry_order(left,right,3)
            self.fixture(right,False)
            ctx=json.loads((right/'junction_context.json').read_text())
            ctx['median_spacing_source']='different-median'
            (right/'junction_context.json').write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,'median_spacing_source'):
                comparison.audit_entry_order(left,right,3)
            self.fixture(right,False)
            frames=[json.loads(s) for s in (right/'video_frames.jsonl').read_text().splitlines()]
            frames[1]['time_s']=0.06
            (right/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
            with self.assertRaisesRegex(ValueError,'frame join'):
                comparison.audit_entry_order(left,right,3)
            self.fixture(right,False)
            with self.assertRaisesRegex(ValueError,'Full comparison duration'):
                comparison.audit_entry_order(left,right,1100)
    def test_median_approaches_construct_both_directions(self):
        def transform(x,y,yaw):return NS(location=NS(x=x,y=y),rotation=NS(yaw=yaw))
        ego_start,ego_entry=transform(-10,5,0),transform(1,5,0)
        other_start,other_entry=transform(5,-10,90),transform(5,1,90)
        waypoints={
            (-10,5):NS(road_id=11,lane_id=-1,is_junction=False),
            (1,5):NS(road_id=11,lane_id=-1,is_junction=True,get_junction=lambda:NS(id=5)),
            (5,-10):NS(road_id=22,lane_id=-1,is_junction=False),
            (5,1):NS(road_id=22,lane_id=-1,is_junction=True,get_junction=lambda:NS(id=5)),
        }
        world_map=NS(get_waypoint=lambda loc,project_to_road=False:waypoints.get((loc.x,loc.y)))
        polygon=[[0,0],[10,0],[10,10],[0,10]]
        args=(world_map,ego_start,ego_entry,other_start,other_entry,polygon,5,'reviewed-polygon','reviewed-entrances')
        plan=geometry.plan_approaches(*args)
        self.assertEqual(plan['approaches']['ego']['road_id'],11)
        self.assertEqual(plan['approaches']['other']['road_id'],22)
        self.assertFalse(plan['statutory_same_crossing_verified'])
        with self.assertRaisesRegex(ValueError,'heading'):
            geometry.plan_approaches(world_map,ego_start,ego_entry,transform(5,-10,-90),other_entry,polygon,5,'polygon','entrances')
        waypoints[(5,1)]=NS(road_id=22,lane_id=-1,is_junction=True,get_junction=lambda:NS(id=6))
        with self.assertRaisesRegex(ValueError,'selected Native junction'):
            geometry.plan_approaches(*args)
        waypoints[(5,1)]=NS(road_id=22,lane_id=-1,is_junction=True,get_junction=lambda:NS(id=5))
        waypoints[(5,-10)]=NS(road_id=11,lane_id=-1,is_junction=False)
        with self.assertRaisesRegex(ValueError,'Different Native approach roads'):
            geometry.plan_approaches(*args)
        waypoints[(5,-10)]=NS(road_id=22,lane_id=-1,is_junction=False)
        devices=[];events=[]
        world=NS(get_map=lambda:world_map,
                 get_actors=lambda:NS(filter=lambda pattern:devices),
                 try_spawn_actor=lambda blueprint,where:(events.append(('spawn',blueprint,where)) or NS(destroy=lambda:events.append(('destroy',)))))
        construction_args=(world,ego_start,ego_entry,other_start,other_entry,'vehicle',polygon,5,'reviewed-polygon','reviewed-entrances')
        with native.construct_crossing_candidate(*construction_args) as (candidate,actor):
            self.assertIsNotNone(actor)
            self.assertEqual(candidate['device_inventory']['native_controlling_device_ids'],[])
        self.assertEqual([event[0] for event in events],['spawn','destroy'])
        devices.append(NS(id=8,get_affected_lane_waypoints=lambda:[NS(road_id=11,lane_id=-1)]))
        with self.assertRaisesRegex(ValueError,'Official device governs'):
            with native.construct_crossing_candidate(*construction_args):pass
        self.assertEqual([event[0] for event in events],['spawn','destroy'])
    def test_native_original_body_capture_and_frame_join(self):
        def actor(actor_id,x,y):
            location=NS(x=x,y=y)
            corners=[NS(x=a,y=b) for a,b in body(x,y)]
            return NS(id=actor_id,get_location=lambda:location,
                      get_transform=lambda:NS(location=location,rotation=NS(yaw=0.0)),
                      get_velocity=lambda:NS(x=1.0,y=0.0,z=0.0),
                      bounding_box=NS(get_world_vertices=lambda transform:corners))
        plan={'candidate_same_native_junction':True,'native_junction_id':5,
              'approaches':{'ego':{'road_id':11},'other':{'road_id':22}}}
        world_map=NS(get_waypoint=lambda location,project_to_road=False:
                     NS(road_id=11 if location.y==5 else 22,lane_id=-1,is_junction=False))
        frame_map=NS(append=lambda frame,time:{'video_frame':7,'carla_frame':frame,'time_s':time})
        snapshot=NS(frame=107,timestamp=NS(elapsed_seconds=5.35))
        stream=io.StringIO()
        recorded=capture.record_crossing_sample(frame_map,stream,snapshot,world_map,
                                                actor(1,-4,5),actor(2,5,-4),plan)
        row=json.loads(stream.getvalue())
        self.assertEqual(recorded['video_frame'],7)
        self.assertEqual(row['ego']['actor_id'],1)
        self.assertEqual(row['ego']['heading_deg'],0.0)
        self.assertEqual(row['other']['road_id'],22)
        self.assertEqual(row['ego']['body_vertices_xy_m'],body(-4,5))
        self.assertEqual(row['ego_vertices_m'],row['ego']['body_vertices_xy_m'])
        self.assertEqual(row['time_s'],5.35)
        stream=io.StringIO()
        with self.assertRaisesRegex(ValueError,'Distinct Native participants'):
            capture.record_crossing_sample(frame_map,stream,snapshot,world_map,
                                           actor(1,-4,5),actor(1,5,-4),plan)
        self.assertEqual(stream.getvalue(),'')
    def test_saved_finalizer_rebuilds_channels_from_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root,True)
            config={'selected_case_id':'testing__C125714__NRS-484B-250-1__motor_vehicle_driver__source_verified_precedence',
                    'law_id':'NRS-484B-250-1','cell_id':'C125714',
                    'expected_other_enters_before_ego':True,
                    'recording_description':{'channels':[]},
                    'physical_completion':{'context_sources':['junction_context.json'],
                                           'body_key':'ego_vertices_m'}}
            (root/'config.json').write_text(json.dumps(config))
            (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':100+i,'time_s':i*.05})+'\n' for i in range(3)))
            (root/'controller_history.jsonl').write_text(''.join(json.dumps({
                'frame':100+i,'time_s':i*.05,'selected_case_id':config['selected_case_id'],
                'ego_held':True,'other_body_inside_before_tick':i>0,
                'other_entered_once_before_tick':i>0,'precedence_hold':True})+'\n'
                for i in range(3)))
            (root/'capture').mkdir();(root/'capture/evidence.jsonl').write_text('{}\n')
            for name in finalizer.CAMERAS:(root/name).write_bytes(b'diagnostic placeholder')
            bad=root/'missing-source'
            bad.mkdir()
            for name in ('config.json','junction_context.json','video_frames.jsonl',
                         'trace.jsonl',*finalizer.CAMERAS):
                shutil.copy2(root/name,bad/name)
            (bad/'capture').mkdir()
            shutil.copy2(root/'capture/evidence.jsonl',bad/'capture/evidence.jsonl')
            with self.assertRaisesRegex(ValueError,'Missing required source: crossing_history.jsonl'):
                finalizer.finalize(bad,bad/'analysis.json')
            output=root/'analysis.json'
            analysis=finalizer.finalize(root,output)
            from worker_exchange.measurement_contract import validate,verify_report
            plan=json.loads((ROOT/'case-plan.json').read_text())
            contract=json.loads((ROOT/'measurement-contract.json').read_text())
            validate(contract,plan['requirement_dispositions'],
                     (ROOT/'finalizer.py').read_text(),config['selected_case_id'])
            self.assertEqual(len(verify_report(contract,analysis,root)),5)
            result=json.loads((root/'result.json').read_text())
            entry=analysis['measurements']['body_entry_order']
            self.assertTrue(entry['value']['other_enters_before_ego'])
            self.assertEqual(entry['sources']['crossing_history.jsonl'],
                             hashlib.sha256((root/'crossing_history.jsonl').read_bytes()).hexdigest())
            self.assertEqual(analysis['measurements']['device_exclusion_context']['value']
                             ['subsection_4_qualification'],'unresolved')
            self.assertEqual(analysis['measurements']['crossing_identity']['value']
                             ['legal_conclusion'],'unresolved')
            self.assertEqual(analysis['measurements']['yield_control_attempt']['value']
                             ['ego_held_frames'],3)
            rows=[json.loads(line) for line in (root/'controller_history.jsonl').read_text().splitlines()]
            rows[1]['ego_held']=False
            (root/'controller_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'released ego before other clearance'):
                finalizer.measure_yield_control(measure.analyze(root),root,config['selected_case_id'])
            self.assertTrue(result['measured_values']['other_body_inside_at_ego_entry'])
            self.assertFalse(result['physical_acceptance_claimed'])
            self.assertEqual(len((root/'channels/ego_inside.jsonl').read_text().splitlines()),3)
            with self.assertRaisesRegex(ValueError,'Retain previous finalization'):
                finalizer.finalize(root,root/'again.json')
    def test_runner_config_and_four_camera_actor_ownership(self):
        pose=[0.0,0.0,2.0,0.0]
        config={'selected_case_id':runner.CASE,'law_id':'NRS-484B-250-1','cell_id':'C125714',
                'rate_hz':20,'duration_s':55,'expected_other_enters_before_ego':True,
                'required_atoms':[],'recording_description':{'channels':[]},
                'physical_completion':{'context_sources':['junction_context.json'],'body_key':'ego_vertices_m'},
                'ego_release_frame':150,'other_release_frame':50,
                'ego_target_speed_mps':4.0,'other_target_speed_mps':4.0,
                'site':{'native_map_name':'TownX','crossing_id':5,
                        'ego_highway_id':1,'other_highway_id':2,
                        'polygon_source':'polygon.txt','entrance_source':'entrances.txt',
                        'median_spacing_source':'median.txt','device_review_source':'devices.txt',
                        'statutory_crossing_review_source':'statutory.txt',
                        'same_statutory_crossing_reviewed':True,
                        'selected_roadway_index':0,
                        'crossing_polygon_xy_m':[[0,0],[10,0],[10,10],[0,10]],
                        'ego_approach':[-5,5,2,0],'ego_entry':[1,5,2,0],
                        'other_approach':[5,-5,2,90],'other_entry':[5,1,2,90],
                        'routes':{'ego':[[-5,5],[1,5],[15,5]],
                                  'other':[[5,-5],[5,1],[5,15]]},
                        'cameras':{name:[0,0,5,0,-20,0] for name in runner.CAMERAS}}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);documents={}
            for key in ('polygon_source','entrance_source','median_spacing_source',
                        'device_review_source','statutory_crossing_review_source'):
                name=config['site'][key]
                content=('synthetic '+key+'\n') if key not in ('median_spacing_source','device_review_source') else json.dumps({
                    'format':'worker-median-roadway-geometry','units':'m',
                    'source_description':'synthetic two-roadway fixture',
                    'roadway_polygons_xy_m':[
                        [[0,0],[10,0],[10,10],[0,10]],
                        [[0,20],[10,20],[10,30],[0,30]]]})+'\n' if key=='median_spacing_source' else json.dumps({
                    'format':'worker-median-device-inventory','crossing_id':5,
                    'native_map_name':'TownX','all_entrances_reviewed':True,
                    'review_basis':'synthetic entrance coverage fixture',
                    'entrances':[{'road_id':11,'lane_id':-1,'highway_id':1},
                                 {'road_id':22,'lane_id':-1,'highway_id':2}],
                    'devices':[]})+'\n'
                (root/name).write_text(content)
                documents[key]={'path':name,'sha256':hashlib.sha256(content.encode()).hexdigest()}
            packet={'format':'worker-median-site-review','review_status':'reviewed_candidate',
                    'site':config['site'],'source_documents':documents}
            packet_path=root/'site-review.json';packet_path.write_text(json.dumps(packet))
            config['site_review']={'path':packet_path.name,'sha256':hashlib.sha256(packet_path.read_bytes()).hexdigest()}
            self.assertIs(runner.validate_config(config,root),config)
            self.assertEqual(runner.verify_site_packet(config,root)
                             ['median_spacing_measurement']['roadway_edge_gap_m'],10.0)
            source=root/'config.json';source.write_text(json.dumps(config))
            check=subprocess.run([sys.executable,str(ROOT/'runner.py'),'--config',str(source),'--check'],
                                 check=True,capture_output=True,text=True)
            checked=json.loads(check.stdout)
            self.assertEqual(checked['planned_frames'],1100)
            self.assertFalse(checked['carla_started'])
            for case_id, expected_other_first in runner.ENTRY_ORDER_CASES.items():
                variant=json.loads(json.dumps(config))
                variant['selected_case_id']=case_id
                variant['expected_other_enters_before_ego']=expected_other_first
                self.assertIs(runner.validate_config(variant,root),variant)
                source.write_text(json.dumps(variant))
                checked=json.loads(subprocess.run(
                    [sys.executable,str(ROOT/'runner.py'),'--config',str(source),'--check'],
                    check=True,capture_output=True,text=True).stdout)
                self.assertEqual(checked['case_id'],case_id)
                self.assertFalse(checked['carla_started'])
                variant['expected_other_enters_before_ego']=not expected_other_first
                with self.assertRaisesRegex(ValueError,'entry-order target'):
                    runner.validate_config(variant,root)
            (root/'polygon.txt').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError,'Site source missing or changed: polygon_source'):
                runner.validate_config(config,root)
            (root/'polygon.txt').write_text('synthetic polygon_source\n')
            changed=json.loads(json.dumps(config))
            changed['site']['other_highway_id']=99
            with self.assertRaisesRegex(ValueError,'Site config differs'):
                runner.validate_config(changed,root)
            packet_path.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'packet missing or changed'):
                runner.validate_config(config,root)
        bad=json.loads(json.dumps(config));bad['site']['cameras'].pop('driver_reference')
        with self.assertRaisesRegex(ValueError,'four named camera'):
            runner.validate_config(bad)
        events=[]
        blueprint=NS(set_attribute=lambda key,value:events.append(('attribute',key,value)))
        def spawn(bp,transform,**kwargs):
            events.append(('spawn',transform,kwargs))
            return NS(stop=lambda:events.append(('stop',)),destroy=lambda:events.append(('destroy',)))
        world=NS(get_blueprint_library=lambda:NS(find=lambda name:blueprint),spawn_actor=spawn)
        transforms={name:object() for name in runner.CAMERAS}
        with cameras.source_cameras(world,'ego',transforms) as sensors:
            self.assertEqual(set(sensors),set(runner.CAMERAS))
        spawns=[e for e in events if e[0]=='spawn']
        self.assertEqual(len(spawns),4)
        self.assertEqual(spawns[-1][2],{'attach_to':'ego'})
        self.assertEqual(sum(e[0]=='stop' for e in events),4)
        self.assertEqual(sum(e[0]=='destroy' for e in events),4)
        applied=[]
        vehicle=NS(get_velocity=lambda:NS(x=0.0,y=0.0,z=0.0),
                   apply_control=lambda value:applied.append(value))
        carla=NS(VehicleControl=lambda:NS(throttle=0.0,brake=0.0))
        runner._drive(carla,vehicle,4.0,True)
        runner._drive(carla,vehicle,4.0,False)
        self.assertEqual(applied[0].brake,1.0)
        self.assertEqual(applied[0].throttle,0.0)
        self.assertGreater(applied[1].throttle,0.0)
        queue=__import__('queue').Queue()
        queue.put(NS(frame=100));queue.put(NS(frame=101))
        self.assertEqual(runner._sensor_frame(queue,101).frame,101)
        queue.put(NS(frame=103))
        with self.assertRaisesRegex(ValueError,'skipped'):
            runner._sensor_frame(queue,102)
    def test_lossless_source_encoder_two_frame_decode(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'source.mkv'
            frame=bytes([0,0,255,255])*16*16
            with encoder.FFV1Writer(output,16,16) as writer:
                writer.write(frame);writer.write(frame)
            self.assertEqual(writer.exit_code,0)
            probe=subprocess.run(['ffprobe','-v','error','-count_frames',
                                  '-show_entries','stream=nb_read_frames,codec_name',
                                  '-of','json',str(output)],check=True,capture_output=True,text=True)
            streams=json.loads(probe.stdout)['streams']
            self.assertEqual(streams[0]['codec_name'],'ffv1')
            self.assertEqual(int(streams[0]['nb_read_frames']),2)
    def test_opposite_turn_comparison_rejects_changed_fixed_camera(self):
        with tempfile.TemporaryDirectory() as tmp:
            roots={mode:Path(tmp)/mode for mode in turns.MODES}
            for mode in turns.MODES:turn_fixture.make_source(roots[mode],mode)
            self.assertTrue(turns.audit_trio(roots,1100)['software_comparison_passed'])
            path=roots['makes_left']/'junction_context.json'
            ctx=json.loads(path.read_text());ctx['camera_plan_sha256']='different-camera-plan'
            path.write_text(json.dumps(ctx))
            with self.assertRaisesRegex(ValueError,'Fixed opposite-turn condition changed: camera_plan_sha256'):
                turns.audit_trio(roots,1100)
if __name__=='__main__':unittest.main()
