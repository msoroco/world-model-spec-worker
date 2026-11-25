import importlib.util
import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('c80909_saved_finalizer', ROOT / 'saved_finalizer.py')
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


class FinalizerTests(unittest.TestCase):
    def test_ffv1_full_decode_probe_on_small_cpu_video(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.mkv'
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                       '-i', 'color=c=blue:s=16x16:r=20', '-frames:v', '4',
                       '-c:v', 'ffv1', '-pix_fmt', 'bgr0', str(path)]
            subprocess.run(command, check=True, capture_output=True)
            info = finalizer._video_info(path)
            self.assertEqual(info['nb_read_frames'], '4')
            self.assertEqual(info['codec_name'], 'ffv1')

    def test_original_camera_inventory_bound_to_native_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            context = {'native_map_id': 'TownX',
                       'divided_highway_source': 'reviewed-map',
                       'roadway_boundaries_source': 'reviewed-road',
                       'opening_geometry_source': 'reviewed-gap',
                       'barrier_actors_source': 'Native-vertices',
                       'other_vehicle_source': 'Native-actor',
                       'right_hand_roadway_xy_m': [[0,-10],[30,-10],[30,-2],[0,-2]],
                       'destination_roadway_xy_m': [[0,2],[30,2],[30,10],[0,10]],
                       'dividing_space_xy_m': [[0,-2],[30,-2],[30,2],[0,2]],
                       'opening_xy_m': [[10,-2],[20,-2],[20,2],[10,2]]}
            (root / 'divider_context.json').write_text(json.dumps(context))
            (root / 'review.txt').write_text('CPU source fixture only\n')
            (root / 'site_source_receipt.json').write_text(json.dumps({
                'native_map_name': 'TownX',
                'source_refs': [{'path': 'review.txt',
                                 'sha256': hashlib.sha256((root / 'review.txt').read_bytes()).hexdigest()}]}))
            (root / 'barrier_receipt.json').write_text(json.dumps({
                'opening_xy_m': context['opening_xy_m'],
                'barrier_footprints_xy_m': [
                    [[0,-2],[8,-2],[8,2],[0,2]],
                    [[22,-2],[30,-2],[30,2],[22,2]]],
                'section_axis_offsets_m': [-10,10]}))
            def body(x, y):
                return [[x+dx,y+dy] for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1))]
            rows = []
            for i,(x,y,heading) in enumerate(((0,-5,[1,0]),(12,-5,[1,0]),
                                                (15,0,[.7,.7]),(15,5,[0,1]))):
                rows.append({'frame': 100+i, 'time_s': 1+i*.05,
                             'ego_body_vertices_xy_m': body(x,y),
                             'other_body_vertices_xy_m': body(25,-5),
                             'ego_forward_xy': heading})
            frames = [{'video_frame': i, 'carla_frame': row['frame'],
                       'time_s': row['time_s']} for i,row in enumerate(rows)]
            (root / 'movement_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in frames))
            for name in finalizer.CAMERAS:
                (root / (name + '.mkv')).write_bytes((name + '-fixture').encode())
            def probe(path):
                width, height = finalizer.CAMERAS[path.stem]
                return {'codec_name': 'ffv1', 'width': width, 'height': height,
                        'r_frame_rate': '20/1', 'nb_read_frames': '4'}
            result = finalizer.finalize(root, probe=probe)
            self.assertEqual(len(result['camera_sources']), 4)
            self.assertFalse(result['physical_acceptance_claimed'])
            (root / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing original source camera'):
                finalizer.finalize(root, probe=probe)
            (root / 'approach.mkv').write_bytes(b'fixture')
            def stale_probe(path):
                row = probe(path)
                if path.stem == 'overview': row['nb_read_frames'] = '3'
                return row
            with self.assertRaisesRegex(ValueError, 'frame count differs'):
                finalizer.finalize(root, probe=stale_probe)


if __name__ == '__main__': unittest.main()
