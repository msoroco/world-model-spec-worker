import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
measure=load('crossing_precedence');native=load('native_crossing');comparison=load('comparison_audit');geometry=load('median_geometry')
def body(x,y):return [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
class Tests(unittest.TestCase):
    def fixture(self,root,other_first=True):
        ctx={'native_map_id':'TownX','intersection_id':5,'ego_highway_id':1,'other_highway_id':2,'ego_road_id':11,'other_road_id':22,'crossing_geometry_source':'native-junction','all_entrances_source':'native-road-inventory','official_device_inventory_source':'native-and-camera','median_spacing_source':'native-map','same_statutory_crossing':True,'official_device_controls_crossing':False,'opposite_approach_with_left_turn':False,'intersection_polygon_xy_m':[[0,0],[10,0],[10,10],[0,10]]}
        (root/'junction_context.json').write_text(json.dumps(ctx))
        spots= [((-4,5), (14,5)), ((-4,5),(5,5)),((5,5),(5,5))] if other_first else [((-4,5),(14,5)),((5,5),(14,5)),((5,5),(5,5))]
        rows=[]
        for i,(ego,other) in enumerate(spots):
            rows.append({'frame':100+i,'time_s':i*.05,'ego':{'intersection_id':5,'road_id':11,'body_vertices_xy_m':body(*ego)},'other':{'intersection_id':5,'road_id':22,'body_vertices_xy_m':body(*other)}})
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
if __name__=='__main__':unittest.main()
