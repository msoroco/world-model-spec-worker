import importlib.util,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
ROOT=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
measure=load('crossing_precedence');native=load('native_crossing')
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
if __name__=='__main__':unittest.main()
