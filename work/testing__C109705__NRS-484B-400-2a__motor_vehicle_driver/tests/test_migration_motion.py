import json
import tempfile
import unittest
from pathlib import Path
from migration_left_turn import assess_left_turn


def box(x, y):
    return [[x + dx, y + dy, z] for z in (0, 1.5) for dx, dy in ((-2, -.8), (-2, .8), (2, .8), (2, -.8))]

class MotionEvidenceTests(unittest.TestCase):
    def fixture(self, root, complete=True):
        geometry = {'two_way': True, 'approach_road_id': 1, 'connector_road_id': 13, 'departure_road_id': 4,
                    'intersection_xy_m': [[-7,-7],[7,-7],[7,7],[-7,7]], 'departure_direction_xy': [0,-1]}
        (root/'road_geometry.json').write_text(json.dumps(geometry))
        (root/'config.json').write_text(json.dumps({'selected_case_id':'diagnostic-c109705'}))
        locations = [(-12, 1.75, 1), (-2, -2, 13), (1.75, -12, 4)] if complete else [(-20+i, 1.75, 1) for i in range(3)]
        rows = [{'frame':21714+i, 'time_s':.05*(i+1), 'road_id':road, 'body_vertices_m':box(x,y)} for i,(x,y,road) in enumerate(locations)]
        (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (root/'video_frames.jsonl').write_text(''.join(json.dumps({'carla_frame':r['frame'],'video_frame':i,'time_s':r['time_s']})+'\n' for i,r in enumerate(rows)))
        return rows
    def test_complete_route_and_body_clearance(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root);value=assess_left_turn(root)
            self.assertEqual(value['status'],'met')
            self.assertEqual(value['observed']['clear_departure_frames'],[21716])
            self.assertFalse(value['legal_acceptance_claimed'])
            self.assertTrue(all(len(h)==64 for h in value['sources'].values()))
    def test_valid_approach_only_is_not_complete(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root,False)
            self.assertEqual(assess_left_turn(root)['status'],'not_met')
    def test_missing_evidence_is_unverified(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root);(root/'body_history.jsonl').unlink();value=assess_left_turn(root)
            self.assertEqual(value['status'],'unverified')
            self.assertIn('body_history.jsonl',value['missing'])
    def test_stale_frame_identity_is_unverified(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows=self.fixture(root);rows[2]['frame']=99999
            (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertEqual(assess_left_turn(root)['status'],'unverified')
    def test_connector_label_without_junction_occupancy_does_not_complete(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);rows=self.fixture(root);rows[1]['body_vertices_m']=box(-30,10)
            (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            self.assertEqual(assess_left_turn(root)['status'],'not_met')

    def test_nine_hundred_frame_history_keeps_full_intervals(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);self.fixture(root);rows=[]
            for i in range(900):
                if i<300:x,y,road=-22+i*.04,1.75,1
                elif i<600:x,y,road=-2,-2,13
                else:x,y,road=1.75,-12-(i-600)*.04,4
                rows.append({'frame':21714+i,'time_s':.05*(i+1),'road_id':road,'body_vertices_m':box(x,y)})
            (root/'body_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            (root/'video_frames.jsonl').write_text(''.join(json.dumps({'carla_frame':r['frame'],'video_frame':i,'time_s':r['time_s']})+'\n' for i,r in enumerate(rows)))
            value=assess_left_turn(root)
            self.assertEqual(value['status'],'met')
            self.assertEqual(value['intervals'][0]['start_frame'],21714)
            self.assertEqual(value['intervals'][0]['end_frame'],22613)
            self.assertEqual(len(value['observed']['native_road_id_history']),900)
