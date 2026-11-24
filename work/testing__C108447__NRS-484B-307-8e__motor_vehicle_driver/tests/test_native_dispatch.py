import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(BASE))
from native_dispatch import dispatch
from site_review import verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('TMPDIR'))
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.road = self.root / 'road.xodr'
        self.road.write_text('<OpenDRIVE><header name="site"/></OpenDRIVE>\n')
        self.authority = self.root / 'parcels.json'
        source = {'format': 'original-parcel-authority-v1',
                  'opendrive_sha256': sha(self.road), 'map_name': 'site',
                  'coordinate_frame': 'native-map', 'intersecting_street_id': 'B',
                  'properties': [{'id': 'lot', 'status': 'private',
                                  'authority': 'parcel register',
                                  'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}],
                  'connector_routes': {'lot': [[-3, 5], [5, 5], [13, 5]]}}
        self.authority.write_text(json.dumps(source) + '\n')
        self.review = self.root / 'review.json'
        self.receipt = {'format': 'original-site-review-v1',
                        'opendrive_sha256': sha(self.road),
                        'authority_sha256': sha(self.authority),
                        'map_name': 'site', 'coordinate_frame': 'native-map',
                        'property_id': 'lot', 'reviewed_at': '2026-11-24T00:00:00Z',
                        'source_record_id': 'parcel-register-record',
                        'review': {'reviewer': 'site reviewer',
                                   'source': 'parcel register', 'decision': 'reviewed'}}
        self.review.write_text(json.dumps(self.receipt) + '\n')
        self.case = BASE.name + '__private_bypass'

    def test_review_rejects_resealed_classification_or_stale_map(self):
        self.assertEqual(verify(self.road, self.authority, self.review,
                                property_id='lot')['source_record_id'],
                         'parcel-register-record')
        source = json.loads(self.authority.read_text())
        source['properties'][0]['status'] = 'public'
        self.authority.write_text(json.dumps(source) + '\n')
        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            verify(self.road, self.authority, self.review, property_id='lot')
        self.receipt['authority_sha256'] = sha(self.authority)
        self.receipt['review']['decision'] = 'pending'
        self.review.write_text(json.dumps(self.receipt) + '\n')
        with self.assertRaisesRegex(ValueError, 'separate source review'):
            verify(self.road, self.authority, self.review, property_id='lot')

    def test_owner_exits_before_saved_processing(self):
        events = []
        case = self.case

        class Owner:
            ego = object()
            signal_observer = camera_observer = control_applier = object()

            class Map:
                name = 'site'

                def to_opendrive(self):
                    return road_source

            class World:
                def get_map(self):
                    return Owner.Map()

            world = World()

            def __enter__(self):
                events.append('enter')
                return self

            def __exit__(self, *_):
                events.append('release')

            def release_receipt(self):
                return {'format': 'native-owner-release-v1', 'case_id': case,
                        'world_restored': True, 'actors_released': True,
                        'sensors_released': True, 'readback_passed': True}

        attempt = self.root / 'attempt'
        road_source = self.road.read_text()

        def capture_fn(**kwargs):
            events.append('capture')
            attempt.mkdir()
            return {'case_id': case, 'sample_count': 20,
                    'physical_acceptance_claimed': False}

        def prepare_fn(*args, **kwargs):
            events.append('prepare')
            (attempt / 'road.xodr').write_bytes(self.road.read_bytes())
            (attempt / 'authority.json').write_bytes(self.authority.read_bytes())
            bundle = attempt / 'delivery-bundle.json'
            bundle.write_text(json.dumps({'case_id': case}) + '\n')
            return {'bundle_path': str(bundle)}

        def audit_fn(*args, **kwargs):
            events.append('audit')
            return {'status': 'met'}

        result = dispatch(owner_factory=lambda *_: Owner(),
                          opendrive=self.road, authority=self.authority,
                          review_receipt=self.review, property_id='lot',
                          case_id=case, purpose={}, actor_source={},
                          attempt=attempt, capture_fn=capture_fn,
                          prepare_fn=prepare_fn, audit_fn=audit_fn,
                          expected_frames=20)
        self.assertEqual(events, ['enter', 'capture', 'release', 'prepare', 'audit'])
        self.assertFalse(result['physical_acceptance_claimed'])

    def test_failed_restoration_stops_saved_processing(self):
        class Owner:
            ego = object()
            signal_observer = camera_observer = control_applier = object()

            class Map:
                name = 'site'

                def to_opendrive(self):
                    return road_source

            class World:
                def get_map(self):
                    return Owner.Map()

            world = World()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def release_receipt(self):
                return {'format': 'native-owner-release-v1', 'case_id': self_case,
                        'world_restored': False, 'actors_released': True,
                        'sensors_released': True, 'readback_passed': True}

        self_case = self.case
        road_source = self.road.read_text()
        attempt = self.root / 'attempt'

        def capture_fn(**kwargs):
            attempt.mkdir()
            return {'case_id': self_case, 'sample_count': 20,
                    'physical_acceptance_claimed': False}

        with self.assertRaisesRegex(ValueError, 'release and restoration'):
            dispatch(owner_factory=lambda *_: Owner(),
                     opendrive=self.road, authority=self.authority,
                     review_receipt=self.review, property_id='lot',
                     case_id=self.case, purpose={}, actor_source={},
                     attempt=attempt, capture_fn=capture_fn,
                     prepare_fn=lambda *a, **k: self.fail('saved processing started'),
                     expected_frames=20)

    def test_live_map_mismatch_stops_capture_and_releases_owner(self):
        events = []

        class Owner:
            ego = object()

            class Map:
                name = 'site'

                def to_opendrive(self):
                    return '<OpenDRIVE><header name="different"/></OpenDRIVE>'

            class World:
                def get_map(self):
                    return Owner.Map()

            world = World()

            def __enter__(self):
                events.append('enter')
                return self

            def __exit__(self, *_):
                events.append('release')

        with self.assertRaisesRegex(ValueError, 'live Native map differs'):
            dispatch(owner_factory=lambda *_: Owner(),
                     opendrive=self.road, authority=self.authority,
                     review_receipt=self.review, property_id='lot',
                     case_id=self.case, purpose={}, actor_source={},
                     attempt=self.root / 'attempt',
                     capture_fn=lambda **k: self.fail('capture started'))
        self.assertEqual(events, ['enter', 'release'])

    def test_capture_exception_releases_owner_without_saved_processing(self):
        events = []
        road_source = self.road.read_text()

        class Owner:
            ego = object()
            signal_observer = camera_observer = control_applier = object()

            class Map:
                name = 'site'

                def to_opendrive(self):
                    return road_source

            class World:
                def get_map(self):
                    return Owner.Map()

            world = World()

            def __enter__(self):
                events.append('enter')
                return self

            def __exit__(self, *_):
                events.append('release')

            def release_receipt(self):
                raise AssertionError('release receipt read after failed capture')

        def failed_capture(**_):
            events.append('capture')
            raise RuntimeError('Native sensor failed')

        with self.assertRaisesRegex(RuntimeError, 'Native sensor failed'):
            dispatch(owner_factory=lambda *_: Owner(),
                     opendrive=self.road, authority=self.authority,
                     review_receipt=self.review, property_id='lot',
                     case_id=self.case, purpose={}, actor_source={},
                     attempt=self.root / 'attempt', capture_fn=failed_capture,
                     prepare_fn=lambda *a, **k: self.fail('saved processing started'))
        self.assertEqual(events, ['enter', 'capture', 'release'])

    def test_saved_source_change_fails_before_pixel_audit(self):
        class Owner:
            ego = object()
            signal_observer = camera_observer = control_applier = object()

            class Map:
                name = 'site'

                def to_opendrive(self):
                    return road_source

            class World:
                def get_map(self):
                    return Owner.Map()

            world = World()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def release_receipt(self):
                return {'format': 'native-owner-release-v1', 'case_id': case,
                        'world_restored': True, 'actors_released': True,
                        'sensors_released': True, 'readback_passed': True}

        case = self.case
        road_source = self.road.read_text()
        attempt = self.root / 'attempt'

        def capture_fn(**kwargs):
            attempt.mkdir()
            return {'case_id': case, 'sample_count': 20,
                    'physical_acceptance_claimed': False}

        def prepare_fn(*args, **kwargs):
            (attempt / 'road.xodr').write_text(road_source)
            source = json.loads(self.authority.read_text())
            source['properties'][0]['status'] = 'public'
            (attempt / 'authority.json').write_text(json.dumps(source) + '\n')
            return {'bundle_path': str(attempt / 'delivery-bundle.json')}

        with self.assertRaisesRegex(ValueError, 'source hash differs'):
            dispatch(owner_factory=lambda *_: Owner(),
                     opendrive=self.road, authority=self.authority,
                     review_receipt=self.review, property_id='lot',
                     case_id=case, purpose={}, actor_source={},
                     attempt=attempt, capture_fn=capture_fn,
                     prepare_fn=prepare_fn,
                     audit_fn=lambda *a, **k: self.fail('pixel audit started'),
                     expected_frames=20)


if __name__ == '__main__':
    unittest.main()
