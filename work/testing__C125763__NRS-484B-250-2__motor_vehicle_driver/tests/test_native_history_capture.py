import hashlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from PIL import Image


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from native_history_capture import capture, audit_media, CAMERAS
from crossing_timing import measure
from saved_finalizer import finalize
from encode_views import encode, compose_primary, main as encode_main
from delivery_audit import audit as audit_delivery
from postprocess import run as postprocess_run


class Vertex:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Box:
    def get_world_vertices(self, transform):
        x, y = transform
        return [Vertex(x + dx, y + dy, z) for dx in (-.4, .4)
                for dy in (-.4, .4) for z in (-.5, .5)]


class Actor:
    bounding_box = Box()

    def __init__(self, world, actor_id, positions):
        self.world, self.id, self.positions = world, actor_id, positions

    def get_transform(self):
        return self.positions[self.world.index], 0


class Map:
    def to_opendrive(self):
        return "<OpenDRIVE/>\n"


class World:
    def __init__(self):
        self.index = -1
        self.map = Map()
        self.settings = type("Settings", (), {"synchronous_mode": True,
                                              "fixed_delta_seconds": .05})()

    def get_map(self):
        return self.map

    def get_settings(self):
        return self.settings

    def tick(self):
        self.index += 1
        return 100 + self.index

    def get_snapshot(self):
        return type("Snapshot", (), {"frame": 100 + self.index,
                                      "timestamp": type("Timestamp", (), {
                                          "elapsed_seconds": self.index * .05})()})()


class CaptureTest(unittest.TestCase):
    def setUp(self):
        scratch = PACKAGE.parents[1] / '.runtime-work' / 'c125763-finalizer-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        for name in ("device", "highway"):
            (self.root / (name + ".txt")).write_text(name + " original fixture\n")
        self.scene = {
            "map_sha256": hashlib.sha256(self.world.map.to_opendrive().encode()).hexdigest(),
            "reviewer": "fixture reviewer", "source_citation": "fixture only",
            "cell_id": "C125763", "control": "yield_sign", "ego_highway": "A",
            "other_highway": "B", "approach_relation": "crossing", "ego_side": "left",
            "intersection_bounds_xy_m": [0, -1, 2, 1],
            "camera_dimensions": {name: [2, 2] for name in CAMERAS},
            "ego_route": [[-5, 0, 0], [-1, 0, 0]],
            "other_route": [[0, -5, 0], [0, -1, 0]],
            "ego_blueprint": "vehicle.ego", "other_blueprint": "vehicle.other",
        }
        for name in ("device", "highway"):
            path = self.root / (name + ".txt")
            self.scene[name + "_source"] = {
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "citation": "fixture only"}
        self.packet = self.root / "reviewed-site.json"
        self.packet.write_text(json.dumps(self.scene) + "\n")
        self.ego = Actor(self.world, 10, [-2, -1, 0, 1])
        self.other = Actor(self.world, 11, [-2, -2, -1, 0])

    def test_original_clock_and_footprints_feed_measurement(self):
        output = self.root / "capture"
        receipt = capture(self.world, self.packet, self.ego, self.other, output, 4)
        self.assertEqual((receipt["first_frame"], receipt["last_frame"]), (100, 103))
        self.assertEqual(receipt["source_manifest"]["road.xodr"]["kind"], "original_native")
        timing = measure(output)
        self.assertAlmostEqual(timing["intersection_entry_time_difference_s"], -.05)
        self.assertFalse(timing["legal_verdict_claimed"])
        with self.assertRaisesRegex(ValueError, "destination"):
            capture(self.world, self.packet, self.ego, self.other, output, 4)

    def test_20_hz_and_identity_required_before_capture(self):
        self.world.settings.fixed_delta_seconds = .1
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)
        self.world.settings.fixed_delta_seconds = .05
        with self.assertRaisesRegex(ValueError, "differ"):
            capture(self.world, self.packet, self.ego, self.ego, self.root / "bad", 4)

    def test_stale_reviewed_device_source_rejected(self):
        (self.root / "device.txt").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)

    def test_missing_intersection_bounds_rejected(self):
        del self.scene["intersection_bounds_xy_m"]
        self.packet.write_text(json.dumps(self.scene) + "\n")
        with self.assertRaisesRegex(ValueError, "bounds"):
            capture(self.world, self.packet, self.ego, self.other, self.root / "bad", 4)

    def test_saved_finalizer_seals_timing_and_rejects_stale_source(self):
        attempt = self.root / 'capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4)
        manifest = attempt / 'source-manifest.json'
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        output = self.root / 'entry-result.json'
        result = finalize(attempt, output, expected_manifest_sha256=digest,
                          probe_id='entry_inside')
        self.assertEqual(result['original_frame_count'], 4)
        self.assertTrue(result['diagnostic_fixture'])
        self.assertFalse(result['legal_verdict_claimed'])
        with self.assertRaises(FileExistsError):
            finalize(attempt, output, expected_manifest_sha256=digest,
                     probe_id='entry_inside')
        with self.assertRaisesRegex(ValueError, 'manifest hash mismatch'):
            finalize(attempt, self.root / 'stale.json',
                     expected_manifest_sha256='0'*64, probe_id='entry_inside')

    def test_saved_finalizer_rejects_changed_original_history(self):
        attempt = self.root / 'capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4)
        manifest = attempt / 'source-manifest.json'
        digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
        with (attempt / 'ego-body-history.jsonl').open('a') as stream:
            stream.write('{}\n')
        with self.assertRaisesRegex(ValueError, 'stale original Native source'):
            finalize(attempt, self.root / 'result.json',
                     expected_manifest_sha256=digest, probe_id='entry_inside')

    def test_full_length_fixture_stays_diagnostic(self):
        self.ego.positions = [-2, -1, 0, 1] + [1] * 896
        self.other.positions = [-2, -2, -1, 0] + [0] * 896
        attempt = self.root / 'long-fixture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 900)
        digest = hashlib.sha256((attempt / 'source-manifest.json').read_bytes()).hexdigest()
        result = finalize(attempt, self.root / 'long-fixture-result.json',
                          expected_manifest_sha256=digest, probe_id='entry_inside')
        self.assertEqual(result['original_frame_count'], 900)
        self.assertTrue(result['diagnostic_fixture'])

    def test_four_camera_original_clock_and_saved_decode(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), (1, 2, 3)).save(stream, format='PNG')
        body = stream.getvalue()
        readers = {name: lambda frame, image=body: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        dims = {name: (2, 2) for name in CAMERAS}
        output = self.root / 'camera-capture'
        receipt = capture(self.world, self.packet, self.ego, self.other, output, 4,
                          camera_readers=readers, camera_dimensions=dims)
        self.assertEqual(receipt['camera_view_frames'], 16)
        self.assertIn('video_frames.jsonl', receipt['source_manifest'])
        self.assertEqual(audit_media(output, camera_dimensions=dims)['decoded_camera_frames'], 16)
        path = output / 'original-frames/approach-000001.png'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            audit_media(output, camera_dimensions=dims)

    def test_canonical_video_frame_map_is_source_bound(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        image = stream.getvalue()
        readers = {name: lambda frame, image=image: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        attempt = self.root / 'frame-map'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4,
                camera_readers=readers,
                camera_dimensions={name: (2, 2) for name in CAMERAS})
        lines = (attempt / 'video_frames.jsonl').read_text().splitlines()
        self.assertEqual(json.loads(lines[0])['video_frame'], 0)
        (attempt / 'video_frames.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            audit_media(attempt, camera_dimensions={name: (2, 2) for name in CAMERAS})

    def test_rejects_camera_tick_mismatch(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        body = stream.getvalue()
        readers = {name: lambda frame, image=body: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        readers['approach'] = lambda frame: {'frame': frame+1, 'png_bytes': body}
        with self.assertRaisesRegex(ValueError, 'camera frame identity'):
            capture(self.world, self.packet, self.ego, self.other,
                    self.root / 'wrong-camera', 4, camera_readers=readers,
                    camera_dimensions={name: (2, 2) for name in CAMERAS})

    def test_original_camera_symlink_is_not_retained_capture(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        image = stream.getvalue()
        readers = {name: lambda frame, image=image: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        attempt = self.root / 'camera-symlink'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4,
                camera_readers=readers,
                camera_dimensions={name: (2, 2) for name in CAMERAS})
        frame = attempt / 'original-frames/overview-000001.png'
        external = self.root / 'same-original-bytes.png'
        external.write_bytes(frame.read_bytes())
        frame.unlink()
        frame.symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'not a retained file'):
            audit_media(attempt, camera_dimensions={name: (2, 2) for name in CAMERAS})

    def test_original_camera_directory_symlink_is_not_retained_capture(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        image = stream.getvalue()
        readers = {name: lambda frame, image=image: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        attempt = self.root / 'camera-directory-symlink'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4,
                camera_readers=readers,
                camera_dimensions={name: (2, 2) for name in CAMERAS})
        original_dir = attempt / 'original-frames'
        moved_dir = self.root / 'same-original-frames'
        original_dir.rename(moved_dir)
        original_dir.symlink_to(moved_dir, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'not a retained file'):
            audit_media(attempt, camera_dimensions={name: (2, 2) for name in CAMERAS})

    def test_saved_finalizer_reopens_four_camera_source(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), (4, 5, 6)).save(stream, format='PNG')
        image = stream.getvalue()
        readers = {name: lambda frame, image=image: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        output = self.root / 'camera-finalize'
        capture(self.world, self.packet, self.ego, self.other, output, 4,
                camera_readers=readers,
                camera_dimensions={name: (2, 2) for name in CAMERAS})
        digest = hashlib.sha256((output / 'source-manifest.json').read_bytes()).hexdigest()
        result = finalize(output, self.root / 'camera-result.json',
                          expected_manifest_sha256=digest, probe_id='entry_inside')
        self.assertTrue(result['camera_coverage_verified'])
        self.assertEqual(result['camera_audit']['decoded_camera_frames'], 16)
        (output / 'original-frames/overview-000000.png').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            finalize(output, self.root / 'stale-camera-result.json',
                     expected_manifest_sha256=digest, probe_id='entry_inside')

    def test_audited_pngs_encode_lossless_four_views(self):
        stream = io.BytesIO()
        Image.new('RGB', (2, 2), (7, 8, 9)).save(stream, format='PNG')
        image = stream.getvalue()
        readers = {name: lambda frame, image=image: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        attempt = self.root / 'encode-capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4,
                camera_readers=readers,
                camera_dimensions={name: (2, 2) for name in CAMERAS})
        receipt = encode(attempt, self.root / 'encoded',
                         camera_dimensions={name: (2, 2) for name in CAMERAS})
        self.assertEqual(set(receipt['videos']), set(CAMERAS))
        self.assertEqual([item['decoded_frames'] for item in receipt['videos'].values()],
                         [4] * 4)
        self.assertFalse(receipt['physical_acceptance'])
        digest = hashlib.sha256((attempt / 'source-manifest.json').read_bytes()).hexdigest()
        saved = self.root / 'encode-saved-result.json'
        finalize(attempt, saved, expected_manifest_sha256=digest, probe_id='entry_inside')
        delivered = audit_delivery(attempt, saved, self.root / 'encoded', receipt,
                                   probe_id='entry_inside')
        self.assertEqual(delivered['decoded_view_frames'], 16)
        self.assertTrue(delivered['full_video_decode'])
        self.assertFalse(delivered['actual_pixels_verified'])
        damaged = dict(receipt)
        damaged['videos'] = {name: dict(row) for name, row in receipt['videos'].items()}
        damaged['videos']['overview']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'encoded camera bytes differ'):
            audit_delivery(attempt, saved, self.root / 'encoded', damaged,
                           probe_id='entry_inside')

    def test_profile_views_compose_with_pinned_runtime_and_full_decode(self):
        dims = {'overview': [1920, 1080], 'approach': [1280, 720],
                'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}
        self.scene['camera_dimensions'] = dims
        self.packet.write_text(json.dumps(self.scene) + '\n')
        images = {}
        for index, name in enumerate(CAMERAS):
            stream = io.BytesIO()
            Image.new('RGB', tuple(dims[name]), (10 + index, 20, 30)).save(stream, format='PNG')
            images[name] = stream.getvalue()
        readers = {name: lambda frame, image=images[name]: {'frame': frame, 'png_bytes': image}
                   for name in CAMERAS}
        attempt = self.root / 'profile-capture'
        capture(self.world, self.packet, self.ego, self.other, attempt, 4,
                camera_readers=readers, camera_dimensions=dims)
        videos = self.root / 'profile-views'
        receipt = encode(attempt, videos, camera_dimensions=dims)
        composed = compose_primary(attempt, videos, self.root / 'primary.mkv', receipt)
        self.assertEqual(composed['frames'], 4)
        self.assertEqual(composed['dimensions'], [3840, 1800])
        self.assertTrue(composed['full_video_decode'])
        self.assertTrue(composed['diagnostic_fixture'])
        self.assertFalse(composed['physical_acceptance'])
        encoded_receipt = self.root / 'encoded-receipt.json'
        encoded_receipt.write_text(json.dumps(receipt) + '\n')
        cli_receipt = self.root / 'composed-receipt.json'
        with patch.object(sys, 'argv', ['encode_views.py', '--mode', 'compose',
                                       '--attempt', str(attempt), '--videos-dir', str(videos),
                                       '--encoded-receipt', str(encoded_receipt),
                                       '--output', str(self.root / 'primary-cli.mkv'),
                                       '--receipt-output', str(cli_receipt)]):
            with redirect_stdout(io.StringIO()):
                encode_main()
        self.assertEqual(json.loads(cli_receipt.read_text())['frames'], 4)
        digest = hashlib.sha256((attempt / 'source-manifest.json').read_bytes()).hexdigest()
        saved = self.root / 'profile-result.json'
        finalize(attempt, saved, expected_manifest_sha256=digest, probe_id='entry_inside')
        delivered = audit_delivery(attempt, saved, videos, receipt,
                                   probe_id='entry_inside',
                                   primary_path=self.root / 'primary.mkv',
                                   composition_receipt=composed)
        self.assertEqual(delivered['composed_primary']['decoded_frames'], 4)
        self.assertTrue(delivered['composed_primary']['full_decode'])
        altered = dict(composed)
        altered['frame_map_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'composed primary source binding differs'):
            audit_delivery(attempt, saved, videos, receipt, probe_id='entry_inside',
                           primary_path=self.root / 'primary.mkv',
                           composition_receipt=altered)
        package = postprocess_run(attempt, self.root / 'saved-package', 'entry_inside')
        self.assertEqual(package['original_frames'], 4)
        self.assertTrue(package['primary_full_decode'])
        self.assertTrue(package['diagnostic_fixture'])
        self.assertFalse(package['physical_acceptance'])
        with self.assertRaisesRegex(ValueError, 'fresh empty postprocessing output'):
            postprocess_run(attempt, self.root / 'saved-package', 'entry_inside')
        changed = dict(receipt)
        changed['videos'] = {name: dict(row) for name, row in receipt['videos'].items()}
        changed['videos']['overview']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'encoded source video differs'):
            compose_primary(attempt, videos, self.root / 'wrong-primary.mkv', changed)
        outside = self.root / 'same-site-bytes.json'
        site_path = attempt / 'site-context.json'
        site_path.replace(outside)
        site_path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'original source is not a retained file'):
            postprocess_run(attempt, self.root / 'symlinked-site-package', 'entry_inside')


if __name__ == "__main__":
    unittest.main()
