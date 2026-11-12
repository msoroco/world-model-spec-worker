import importlib.util
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('one_way_finalizer', ROOT/'one_way_finalizer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SourceJoinTests(unittest.TestCase):
    def make_sources(self, root):
        root = Path(root)
        (root/'native').mkdir()
        site={'curb_source':'native/map edge','one_way_source':'native/OpenDRIVE lane',
              'turn_left_edge_polyline_xy':[[-6,-10],[-6,-6],[-10,-6]]}
        (root/'site.json').write_text(json.dumps(site))
        site_sha=hashlib.sha256((root/'site.json').read_bytes()).hexdigest()
        frames = [{'video_frame': i, 'carla_frame': 100+i, 'native_frame': 100+i, 'time_s': i*.05,
                   'subject_actor_id': 7} for i in range(3)]
        bodies = [dict(video_frame=i, carla_frame=100+i, native_frame=100+i, actor_id=7,
                       road_id=('approach','connector','departure')[i],
                       body_corners_xy=[[-5.4,-20],[-3.6,-20],[-3.6,-16],[-5.4,-16]]
                       if i == 0 else ([[-5.4,-5.4],[-3.6,-5.4],[-3.6,-3.6],[-5.4,-3.6]]
                       if i == 1 else [[-20,-5.4],[-16,-5.4],[-16,-3.6],[-20,-3.6]]))
                  for i in range(3)]
        edges = [dict(video_frame=i, carla_frame=100+i, native_frame=100+i,
                      road_id=('approach','connector','departure')[i],
                      native_road_direction=('north','turn','west')[i],
                      observed_left_curb_x=-6 if i == 0 else None,
                      observed_left_curb_y=-6 if i == 2 else None,
                      turn_left_edge_polyline_xy=[[-6,-10],[-6,-6],[-10,-6]],
                      site_file_sha256=site_sha,
                      one_way_source='native/OpenDRIVE lane', curb_source='native/map edge')
                 for i in range(3)]
        for name, rows in [('video_frames.jsonl',frames),
                           ('native/footprints.jsonl',bodies),
                           ('native/road_edges.jsonl',edges)]:
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        return root, frames, bodies, edges

    def test_saved_original_measurement(self):
        with TemporaryDirectory() as folder:
            root, _, _, _ = self.make_sources(folder)
            result = module.finalize(root)
            self.assertEqual(result['original_frame_count'], 3)
            self.assertAlmostEqual(result['minimum_approach_gap_m'], .6)
            self.assertAlmostEqual(result['minimum_departure_gap_m'], .6)
            self.assertGreater(result['minimum_turn_gap_m'], 0)
            self.assertEqual(len(result['source_sha256']), 4)
            self.assertEqual(result['legal_practicability_judgment'], 'unresolved')

    def test_missing_and_stale_sources_rejected(self):
        with TemporaryDirectory() as folder:
            root, frames, bodies, edges = self.make_sources(folder)
            (root/'native/road_edges.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'missing original source'):
                module.finalize(root)
            (root/'native/road_edges.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in edges))
            bodies[1]['native_frame'] = bodies[1]['carla_frame'] = 999
            (root/'native/footprints.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in bodies))
            with self.assertRaisesRegex(ValueError, 'join incomplete'):
                module.finalize(root)

    def test_actor_road_and_source_conflicts_rejected(self):
        with TemporaryDirectory() as folder:
            root, frames, bodies, edges = self.make_sources(folder)
            bodies[1]['actor_id'] = 8
            (root/'native/footprints.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in bodies))
            with self.assertRaisesRegex(ValueError, 'actor identity'):
                module.finalize(root)
            bodies[1]['actor_id'] = 7
            edges[1]['curb_source'] = ''
            (root/'native/footprints.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in bodies))
            (root/'native/road_edges.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in edges))
            with self.assertRaisesRegex(ValueError, 'curb source'):
                module.finalize(root)


if __name__ == '__main__':
    unittest.main()
