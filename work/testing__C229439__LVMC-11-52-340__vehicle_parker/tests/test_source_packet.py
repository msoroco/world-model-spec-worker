import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from city_space import CASES, SOURCE_FIELDS
from source_packet import ASSIGNMENT, load_reviewed
from native_capture import acquire


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReviewedSourceTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'c229439-source-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        case = CASES[0]
        self.case_id = ASSIGNMENT + '__' + case.name
        scene = {'cell_id': 'C229439', 'actor': 'vehicle_parker',
                 'vehicle_id': 'source-v1', 'parking_person_id': 'source-p1',
                 'city_location_kind': 'city_street',
                 'city_vehicle': case.city_vehicle, 'designated': case.designated,
                 'posted': case.posted, 'inside_space': case.inside_space,
                 'governed_space_rect_m': [0, 0, 3, 6],
                 'vehicle_footprint_rect_m': [.2, .2, 2, 4],
                 'parking_route_xy': [[-2, -2], [1, 1]],
                 'park_start_frame': 100,
                 'official_device_text': 'City vehicles only',
                 'city_vehicle_authority_ref': 'reviewed fleet record',
                 'council_designation_ref': 'reviewed Council record'}
        sources = {}
        for field in SOURCE_FIELDS:
            path = self.root / (field + '.json')
            path.write_text(json.dumps({'field': field, 'case_id': self.case_id,
                                        'reviewer': 'test reviewer'}) + '\n')
            sources[field] = {'path': path.name, 'sha256': sha(path),
                              'citation': 'synthetic CPU test only',
                              'reviewer': 'test reviewer'}
            scene[field + '_source_sha256'] = sha(path)
        self.packet = {'format': 'c229439-reviewed-city-space-v1',
                       'assignment_id': ASSIGNMENT, 'case_id': self.case_id,
                       'reviewer': 'test reviewer',
                       'review_citation': 'synthetic CPU test only',
                       'sources': sources, 'scene': scene,
                       'camera_plan': {name: {'source_transform': [0, 0, 2],
                                              'purpose': name} for name in
                                       ('overview', 'approach', 'reference_corner',
                                        'driver_reference')}}
        self.packet_path = self.root / 'packet.json'
        self.save()

    def save(self):
        self.packet_path.write_text(json.dumps(self.packet) + '\n')

    def test_reviewed_sources_bind_exact_case(self):
        _, scene, case = load_reviewed(self.packet_path, self.case_id)
        self.assertEqual(case, CASES[0])
        self.assertEqual(scene['vehicle_id'], 'source-v1')

    def test_changed_authority_bytes_rejected(self):
        (self.root / 'city_vehicle_authority.json').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'bytes missing or changed'):
            load_reviewed(self.packet_path, self.case_id)

    def test_other_case_or_unsigned_scene_rejected(self):
        with self.assertRaisesRegex(ValueError, 'another case'):
            load_reviewed(self.packet_path, ASSIGNMENT + '__' + CASES[1].name)
        self.packet['scene']['city_vehicle_authority_source_sha256'] = 'wrong'
        self.save()
        with self.assertRaisesRegex(ValueError, 'scene source hash changed'):
            load_reviewed(self.packet_path, self.case_id)

    def test_source_path_traversal_rejected(self):
        self.packet['sources']['city_location']['path'] = '../outside.json'
        self.save()
        with self.assertRaisesRegex(ValueError, 'relative original source'):
            load_reviewed(self.packet_path, self.case_id)

    def test_camera_join_failure_restores_world_and_owned_actors(self):
        class Adapter:
            def __init__(self):
                self.destroyed = []
                self.aborted = False
                self.restored = False

            def spawn_device(self, text, bounds):
                return 'device'

            def spawn_vehicle(self, position):
                return 'vehicle'

            def set_parking_route(self, vehicle, route, frame):
                pass

            def pipeline_client(self):
                return self

            def start_cameras(self, output, plan):
                pass

            def advance_parking(self, built, index):
                pass

            def tick_world(self):
                return 100, 5.

            def camera_frame_ids(self, frame):
                return {'overview': frame}

            def abort_cameras(self):
                self.aborted = True

            def destroy(self, actor):
                self.destroyed.append(actor)

            def restore_world(self):
                self.restored = True
                return True

        class Pipeline:
            def __init__(self, *args, **kwargs):
                self.closed = False

            def close(self, confirmed):
                self.closed = True

        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, 'camera frames do not join'):
            acquire(adapter, self.packet_path, self.case_id,
                    self.root / 'attempt', pipeline_factory=Pipeline,
                    seal_factory=lambda *args, **kwargs: None)
        self.assertEqual(adapter.destroyed, ['vehicle', 'device'])
        self.assertTrue(adapter.aborted)
        self.assertTrue(adapter.restored)


if __name__ == '__main__':
    unittest.main()
