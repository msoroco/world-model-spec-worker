import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace as N

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'runtime/scenario_pipeline'))
from one_way_native_capture import OneWayNativeCapture, read_curb_source
from one_way_finalizer import finalize
from runner import check_config


class TestOriginalTurnCapture(unittest.TestCase):
    def site(self, root):
        path = root/'site.json'
        path.write_text(json.dumps({'opendrive_sha256': 'map-hash', 'source_id': 'fixture-site',
            'one_way_source': 'fixture one-way map survey',
            'curb_source': 'fixture physical-edge survey',
            'approach_left_curb_x': -6., 'departure_left_curb_y': -6.}))
        return path

    def test_original_writer_joins_both_road_curb_samples(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); site = self.site(path)
            transform = N(location=N(x=-4.5,y=0.), rotation=N(yaw=90.))
            actor = N(id=7, is_alive=True,
                      get_transform=lambda: transform,
                      bounding_box=N(get_world_vertices=lambda tr: [N(x=-5.4,y=-5.4)]*8))
            world_map = N(get_waypoint=lambda loc: N(road_id=1 if transform.rotation.yaw==90 else 2))
            writer = OneWayNativeCapture(path, actor, world_map,
                {'opendrive_sha256':'map-hash'}, site)
            writer.append(100, 0.)
            transform.rotation.yaw = 180.
            writer.append(101, .05)
            writer.close()
            measured = finalize(path)
            self.assertAlmostEqual(measured['minimum_approach_gap_m'], .6)
            self.assertAlmostEqual(measured['minimum_departure_gap_m'], .6)
            edge_rows = [json.loads(line) for line in (path/'native/road_edges.jsonl').read_text().splitlines()]
            self.assertEqual([r['native_road_direction'] for r in edge_rows], ['north','west'])
            self.assertEqual(edge_rows[0]['site_file_sha256'], hashlib.sha256(site.read_bytes()).hexdigest())

    def test_rejects_stale_source_and_wrong_heading(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp); site = self.site(path)
            with self.assertRaisesRegex(ValueError, 'surveyed Native map'):
                read_curb_source(site, 'other-map')
            transform = N(location=N(x=0.,y=0.), rotation=N(yaw=0.))
            actor = N(id=7, is_alive=True,
                      get_transform=lambda: transform,
                      bounding_box=N(get_world_vertices=lambda tr: [N(x=0.,y=0.)]*8))
            writer = OneWayNativeCapture(path, actor,
                N(get_waypoint=lambda loc: N(road_id=1)),
                {'opendrive_sha256':'map-hash'}, site)
            with self.assertRaisesRegex(ValueError, 'heading left'):
                writer.append(100,0.)
            writer.close()

    def test_runner_rejects_wrong_exact_case_and_camera_count(self):
        cfg = {'law_id':'NRS-484B-400-5','cell_id':'C152976',
               'actor':'motor_vehicle_driver','case_branch':'left_edge_reference',
               'selected_case_id':'heldout__C152976__NRS-484B-400-5__motor_vehicle_driver__left_edge_reference',
               'rate_hz':20,'frames':160,'duration_s':8,
               'cameras':[{'name':name} for name in ('overview','approach','reference_corner','driver_reference')],
               'site_source':'site.json','vehicle_blueprint_id':'vehicle.test',
               'lateral_scale':1.,'speed_kp':.22,'lookahead_m':3.}
        self.assertTrue(check_config(cfg))
        cfg['cameras'].pop()
        with self.assertRaisesRegex(ValueError, 'Four named'):
            check_config(cfg)


if __name__ == '__main__': unittest.main()
