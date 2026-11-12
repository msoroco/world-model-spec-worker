import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from finalizer import finalize
from yield_context import CAMERAS


class FinalizerTests(unittest.TestCase):
    def sources(self, root):
        shutil.copy(ROOT/'native-map-plan/yield-nearest-view.xodr', root/'road.xodr')
        shutil.copy(ROOT/'config.json', root/'config.json')
        (root/'capture').mkdir()
        (root/'capture/native_map_facts.json').write_text(json.dumps({
            'map': 'yield-native', 'junctions': [{'id': 158191}],
            'crosswalk_vertices_m': []}))
        (root/'capture/evidence.jsonl').write_text('{}\n')
        (root/'road_context.json').write_text(json.dumps({
            'native_map_id': 'yield-native', 'intersection_id': 158191,
            'approach_road_id': 158190, 'approach_lane_id': -1,
            'through_highway_id': 158195, 'native_yield_sign_id': 12,
            'no_stop_line': None, 'no_near_crosswalk': None,
            'police_control': None, 'traffic_signal_control': None}))
        frames = [{'video_frame': i, 'carla_frame': 100+i, 'time_s': 5+i*.05}
                  for i in range(2)]
        (root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in frames))
        controls = [{'frame': r['carla_frame'],
                     'yield_sign': {'actor_id': 12, 'blueprint': 'traffic.yield',
                                    'trigger_vertices_m': [[0,0,0]]*4},
                     'native_crosswalk_vertices_m': [], 'competing_controls': []}
                    for r in frames]
        (root/'control_inventory.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in controls))
        for name in CAMERAS:
            (root/name).write_bytes(b'cpu-only diagnostic image placeholder')
        review = {'method': 'original_source_camera_frame_review',
                  'reviewer': 'cpu-test-source-review', 'reviewed_frame_count': 2,
                  'reviewed_carla_frames': [100,101],
                  'first_carla_frame': 100, 'last_carla_frame': 101,
                  'source_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
                                    for name in CAMERAS},
                  'yield_sign_face_visible': True, 'no_stop_line': True,
                  'no_near_crosswalk': True, 'no_police_direction': True,
                  'no_traffic_signal_control': True}
        (root/'rendered_marking_review.json').write_text(json.dumps(review))
        history = [{'frame': 100, 'time_s': 5, 'road_id': 158190, 'lane_id': -1,
                    'ego_speed_mps': 4, 'distance_to_intersection_m': 15},
                   {'frame': 101, 'time_s': 5.05, 'road_id': 158190, 'lane_id': -1,
                    'ego_speed_mps': 2, 'distance_to_intersection_m': 3}]
        samples = [{'frame': r['frame'], 'distance_to_intersection_m': r['distance_to_intersection_m'],
                    'through_highway_visible': i==1, 'visible_through_vehicle_ids': [23] if i==1 else [],
                    'ray_source': 'visibility_rays.jsonl'} for i,r in enumerate(history)]
        rays = [{'frame': r['frame'], 'distance_to_intersection_m': r['distance_to_intersection_m'],
                 'observer_m': [0,0,1.5], 'target_m': [1.8,0,1.5],
                 'blockers': [] if i==1 else [{'label':'wall','location_m':[1,0,1]}],
                 'clear': i==1, 'visible_through_vehicle_ids': [23] if i==1 else []}
                for i,r in enumerate(history)]
        (root/'approach_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in history))
        (root/'visibility_samples.json').write_text(json.dumps(samples))
        (root/'visibility_rays.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rays))
        (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':r['frame'],'time_s':r['time_s'],
            'position_m':[-20+i,-1.8,0]})+'\n' for i,r in enumerate(history)))
        (root/'control_context.json').write_text(json.dumps({
            'intersection_xy_m': [[-8,-8],[8,-8],[8,8],[-8,8]]}))
        bodies=[{'frame': r['frame'], 'time_s': r['time_s'],
                 'ego': {'body_vertices_m': [[-20+i+j*.01,-1.8,0] for j in range(8)]},
                 'through': None} for i,r in enumerate(history)]
        (root/'interaction_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in bodies))

    def test_saved_analysis_requires_original_review_and_writes_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.sources(root)
            analysis=finalize(root,root/'analysis-report.json')
            self.assertEqual(analysis['measurements']['speed_at_closest_view_mps']['value'],2)
            result=json.loads((root/'result.json').read_text())
            self.assertEqual(result['target_checks'][0]['measured'],2)
            self.assertEqual(result['legal_conclusion'] if 'legal_conclusion' in result else None,None)
            self.assertEqual(len((root/'channels/ego_approach_speed.jsonl').read_text().splitlines()),2)
            sys.path.insert(0, str(ROOT.parents[1]/'runtime/scenario_pipeline'))
            from batch_pipeline.validation import recording_evidence
            recording_evidence(result, json.loads((root/'config.json').read_text())['recording_description'],
                               lambda name: root/name)
            with self.assertRaisesRegex(ValueError,'Retain prior'):
                finalize(root,root/'analysis-report.json')

    def test_missing_or_mismatched_review_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            self.sources(root)
            (root/'rendered_marking_review.json').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                finalize(root,root/'analysis-report.json')
            self.sources_review_only(root)
            (root/CAMERAS[0]).write_bytes(b'changed image')
            with self.assertRaisesRegex(ValueError,'hashes differ'):
                finalize(root,root/'analysis-report.json')

    @staticmethod
    def sources_review_only(root):
        review={'method':'original_source_camera_frame_review','reviewer':'cpu-test',
                'reviewed_frame_count':2,'reviewed_carla_frames':[100,101],
                'first_carla_frame':100,'last_carla_frame':101,
                'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                                 for name in CAMERAS},
                'yield_sign_face_visible':True,'no_stop_line':True,
                'no_near_crosswalk':True,'no_police_direction':True,
                'no_traffic_signal_control':True}
        (root/'rendered_marking_review.json').write_text(json.dumps(review))
