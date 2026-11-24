"""Selected saved analysis uses retained sources and rejects missing originals."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import ASSIGNMENT, VIEWS, build
from native_publication import publish


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root, mode):
    case = ASSIGNMENT + '__' + mode
    write_json(root / 'config.json', {'selected_case_id': case,
                                      'requested_headlamp_mode': mode,
                                      'camera_dimensions': {view: [8, 4] for view in VIEWS}})
    write_json(root / 'site-packet.json', {
        'case_id': case, 'parking_source_ref': 'reviewed-parking-source',
        'intersection_source_ref': 'reviewed-intersection-source'})
    states = [{'frame': i + 100, 'time_s': i / 20, 'speed_mps': 0.0,
               'parking_brake': True, 'footprint_inside_reviewed_parking_polygon': True,
               'light_state_bits': 0 if mode == 'unlit' else 1 if mode == 'low_beam' else 2,
               'actor_id': 17} for i in range(3)]
    maps = [{'frame': i + 100, **{view + '_source_frame': i + 100 for view in VIEWS}}
            for i in range(3)]
    for name, rows in [('actor-state.jsonl', states), ('camera-frame-map.jsonl', maps)]:
        (root / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    media = {}
    for view in VIEWS:
        path = root / (view + '.zip')
        with ZipFile(path, 'w') as archive:
            for frame in range(100, 103):
                image = Image.new('RGB', (8, 4), (30, 30, 30))
                for x in range(3):
                    for y in range(3):
                        image.putpixel((x, y), (150, 150, 150))
                stream = io.BytesIO(); image.save(stream, format='PNG')
                archive.writestr(str(frame) + '.png', stream.getvalue())
        media[view] = {'path': path.name, 'sha256': digest(path), 'source_frame_count': 3}
    write_json(root / 'lamp-roi.json', {'format': 'parked-headlamp-photometry-roi-v1',
        'source_kind': 'reviewed_original_camera_roi', 'source_ref': 'diagnostic-only',
        'camera_view': 'approach', 'dimensions': [8, 4],
        'lamp_polygon_xy': [[0, 0], [2, 0], [2, 2], [0, 2]],
        'background_polygon_xy': [[5, 0], [7, 0], [7, 2], [5, 2]]})
    write_json(root / 'native-source-receipt.json', {
        'case_id': case, 'requested_mode': mode, 'frame_count': 3,
        'site_source_sha256': digest(root / 'site-packet.json'),
        'source_hashes': {name: digest(root / name) for name in
                          ('actor-state.jsonl', 'camera-frame-map.jsonl')},
        'light_masks': {'low_beam': 1, 'high_beam': 2},
        'original_camera_media': media, 'physical_acceptance_claimed': False})


class AnalysisTests(unittest.TestCase):
    def test_three_cases_source_bound_and_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            for mode in ('unlit', 'low_beam', 'high_beam'):
                root = parent / mode; root.mkdir()
                fixture(root, mode)
                report = build(root)
                self.assertEqual(report['case_id'], ASSIGNMENT + '__' + mode)
                self.assertEqual(set(report['measurements']),
                    {'parked_vehicle_observation'} if mode == 'unlit' else
                    {'parked_vehicle_observation', 'lighted_headlamp_observation',
                     'depression_or_dimming_observation'})
                self.assertFalse(report['legal_verdict_claimed'])
                if mode != 'unlit':
                    (root / 'lamp-roi.json').unlink()
                    with self.assertRaisesRegex(ValueError, 'Missing required source: lamp-roi.json'):
                        build(root)
                else:
                    (root / 'actor-state.jsonl').unlink()
                    with self.assertRaisesRegex(ValueError, 'Missing required source: actor-state.jsonl'):
                        build(root)

    def test_native_publication_joins_original_core_and_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, 'low_beam')
            description = {'channels': [{'name': name, 'unit': 'structured record'}
                for name in ('original_actor_state', 'original_four_view_frame_map',
                             'headlamp_emission_and_aim_review')]}
            write_json(root / 'construction.json', {'recording_description': description})
            trace = [{'frame': i + 100, 'time_s': i / 20} for i in range(3)]
            mapping = [{'carla_frame': i + 100, 'video_frame': i, 'time_s': i / 20}
                       for i in range(3)]
            (root / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
            (root / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in mapping))
            receipt = json.loads((root / 'native-source-receipt.json').read_text())
            receipt['original_camera_videos'] = {}
            for view in VIEWS:
                path = root / (view + '.mkv'); path.write_bytes(b'diagnostic-only')
                receipt['original_camera_videos'][view] = {'path': path.name}
            write_json(root / 'native-source-receipt.json', receipt)
            report = build(root)
            result = publish(root, report)
            self.assertEqual(len(result['recording_evidence']), 4)
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['target_checks'][0]['matched'])
            self.assertEqual(result['video_references'], [view + '.mkv' for view in VIEWS])
            with self.assertRaisesRegex(ValueError, 'already published'):
                publish(root, report)


if __name__ == '__main__':
    unittest.main()
