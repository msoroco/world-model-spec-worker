"""Source-shaped synthetic tests; do not assert Native physical success."""
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from measure_saved_30s import measure

class SavedRotation(unittest.TestCase):
    def fixture(self,root,sign):
        root=Path(root);(root/'capture').mkdir()
        (root/'config.json').write_text(json.dumps({'requested_rotation_sign':sign,
            'road_sha256':'a'*64}))
        (root/'native-map-readback.json').write_text(json.dumps({
            'road_sha256':'a'*64,'native_map_sha256':'b'*64,
            'arc_lane_readback':{'-1':{'road_id':1,'lane_id':-1},
                                 '-2':{'road_id':1,'lane_id':-2}}}))
        (root/'capture/manifest.json').write_text(json.dumps({'frames':600}))
        native=[];mapping=[];trace=[];evidence=[]
        for i in range(600):
            theta=-math.pi/2+sign*8*(i+1)/20/23.75
            x=23.75*math.cos(theta);y=23.75*math.sin(theta)
            heading=math.degrees(theta+sign*math.pi/2)
            body=[[x+dx,y+dy,1] for dx in (-1,1) for dy in (-.5,.5) for _ in (0,1)]
            native.append({'frame':i,'native_frame':100+i,'time_s':(i+1)/20,
                'observed_lane_id':-1,'ego':{'center_native_xyz_m':[x,y,1],
                'body_native_xyz_m':body,'blueprint':'vehicle.tesla.model3',
                'actor_id':42,'yaw_deg':heading,'speed_mps':8}})
            mapping.append({'video_frame':i,'native_frame':100+i,'time_s':(i+1)/20})
            trace.append({'frame':100+i,'time_s':(i+1)/20})
            evidence.append({'original_frame':100+i,'recording_time_s':(i+1)/20})
        for name,rows in [('native-raw-actors.jsonl',native),('video_frames.jsonl',mapping),
                          ('trace.jsonl',trace),('capture/evidence.jsonl',evidence)]:
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    def test_both_direction_joins(self):
        for sign in (1,-1):
            with self.subTest(sign=sign),tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as root:
                self.fixture(root,sign);result=measure(root)
                self.assertTrue(result['value']['direction_request_matched'])
                self.assertEqual(result['value']['rotary_lane_samples'],600)
                self.assertEqual(result['value']['physical_roundabout_design_verified'],False)
    def test_missing_and_changed_source_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as root:
            self.fixture(root,1);path=Path(root)/'native-raw-actors.jsonl'
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure(root)
            self.fixture_removed_repair(root)
            path=Path(root)/'video_frames.jsonl';rows=path.read_text().splitlines()
            item=json.loads(rows[10]);item['native_frame']=999;rows[10]=json.dumps(item)
            path.write_text('\n'.join(rows)+'\n')
            with self.assertRaisesRegex(ValueError,'frame/time join differs'):
                measure(root)
    def fixture_removed_repair(self,root):
        # Rebuild only the missing source from a fresh independent diagnostic.
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as source:
            self.fixture(source,1)
            (Path(root)/'native-raw-actors.jsonl').write_bytes(
                (Path(source)/'native-raw-actors.jsonl').read_bytes())
if __name__=='__main__':unittest.main()
