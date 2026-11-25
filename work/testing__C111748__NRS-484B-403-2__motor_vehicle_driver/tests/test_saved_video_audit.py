import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("device_video_test", ROOT / "saved_video_audit.py")
video = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(video)
_spec = importlib.util.spec_from_file_location('device_delivery_full_test', ROOT / 'delivery_audit.py')
delivery = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(delivery)
CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


def render(path, *, frames=900, size="16x16", codec="ffv1", fps=20):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"testsrc2=size={size}:rate={fps}", "-frames:v", str(frames),
                    "-c:v", codec, str(path)], check=True)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.movie = self.root / "overview.mkv"
        render(self.movie)

    def test_full_frame_decode_and_bad_profile(self):
        result = video.decode(self.movie, size=(16, 16))
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual(result["codec"], "ffv1")
        self.assertEqual(len(result["decoded_frames_sha256"]), 64)
        with self.assertRaisesRegex(video.VideoAuditError, "dimensions"):
            video.decode(self.movie, size=(24, 16))

    def test_reject_short_and_lossy_video(self):
        with self.assertRaisesRegex(video.VideoAuditError, "frame count"):
            video.decode(self.movie, size=(16, 16), frames=901)
        lossy = self.root / "lossy.mkv"
        render(lossy, frames=5, codec="mpeg4")
        with self.assertRaisesRegex(video.VideoAuditError, "lossless"):
            video.decode(lossy, size=(16, 16), frames=5)

    def test_reject_wrong_cadence(self):
        wrong = self.root / "wrong.mkv"
        render(wrong, frames=5, fps=10)
        with self.assertRaisesRegex(video.VideoAuditError, "20 Hz"):
            video.decode(wrong, size=(16, 16), frames=5)

    def test_four_camera_attempt_join(self):
        device = {"device_id": 77, "authority_source_sha256": "authority",
                  "legal_consistency_source_sha256": "legal", "display_source_sha256": "display",
                  "governed_approach": "A", "prohibits_u_turn": True}
        rows = []
        for i in range(900):
            rows.append({"frame": 100 + i, "time_s": i / 20,
                         "ego": {"id": 42, "road_id": 1, "lane_id": -1 if i == 899 else 1,
                                 "x": i / 20, "y": 0, "yaw_deg": 180 if i == 899 else 0,
                                 "approach_id": "A", "u_turn_in_progress": i == 600},
                         "device_readback": {"device_id": 77, "prohibits_u_turn": True,
                                             "visible_to_ego": i >= 1},
                         "cameras": {name: 100 + i for name in video.PROFILE}})
        native = {"case_id": CASE, "actor": "motor_vehicle_driver", "map_sha256": "map",
                  "route_sha256": "route", "ego_id": 42,
                  "site_sha256": "site-diagnostic-hash",
                  "site_review_binding": {"case_id": CASE,
                      "site_sha256": "site-diagnostic-hash",
                      "review_sha256": "review-diagnostic-hash",
                      "verified_sources": {name: {"sha256": "source-diagnostic-hash"}
                          for name in ("highway", "placement_authority",
                                       "legal_consistency", "display_direction")}},
                  "highway_status": {"source_sha256": "highway"}, "device": device,
                  "duration_s": 45.0, "diagnostic": False, "frames": rows}
        native_path = self.root / "device-native.json"
        native_path.write_text(json.dumps(native), encoding="utf-8")
        media = {}
        for name in video.PROFILE:
            path = self.root / f"{name}.mkv"
            if path != self.movie:
                path.write_bytes(self.movie.read_bytes())
            media[name] = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        manifest = {"case_id": CASE, "attempt_id": "test-attempt", "recording_id": "test-recording",
                    "acquisition_kind": "original_native",
                    "native": {"path": native_path.name,
                               "sha256": hashlib.sha256(native_path.read_bytes()).hexdigest()},
                    "media": media}
        (self.root / "saved-sources.json").write_text(json.dumps(manifest), encoding="utf-8")
        profile = {name: (16, 16) for name in video.PROFILE}
        receipt = video.audit(self.root, case_id=CASE, profile=profile)
        self.assertTrue(receipt["full_video_decode"])
        self.assertEqual(set(receipt["decoded_media"]), set(video.PROFILE))
        self.assertFalse(receipt["actual_pixels"])
        complete = video._sources.audit_complete(self.root, case_id=CASE, profile=profile)
        self.assertEqual(complete["format"], "worker-saved-source-and-video-integrity")
        self.assertTrue(complete["full_video_decode"])
        self.assertFalse(complete["physical_completion"])
        with self.assertRaisesRegex(delivery.AuditError, 'acquisition-provenance'):
            delivery.audit(self.root, CASE, profile=profile)
        provenance_path = self.root / 'acquisition-provenance.json'
        (self.root / 'capture-seal.json').write_text('{}', encoding='utf-8')
        provenance = {'provenance_kind': 'synthetic', 'diagnostic_fixture': False,
                      'case_id': CASE, 'site_sha256': native['site_sha256']}
        provenance_path.write_text(json.dumps(provenance), encoding='utf-8')
        with self.assertRaisesRegex(delivery.AuditError, 'synthetic'):
            delivery.verify_capture_seal(self.root, CASE, manifest, native)
        provenance['provenance_kind'] = 'native'
        provenance_path.write_text(json.dumps(provenance), encoding='utf-8')
        review_root = self.root / 'original-review'
        source_root = review_root / 'sources'
        source_root.mkdir(parents=True)
        reviewed = {'sources': {name: {'path': name + '.txt'} for name in
                    ('highway', 'placement_authority', 'legal_consistency', 'display_direction')}}
        (review_root / 'review.json').write_text(json.dumps(reviewed), encoding='utf-8')
        (review_root / 'site.json').write_text('{}', encoding='utf-8')
        for ref in reviewed['sources'].values():
            (source_root / ref['path']).write_text('source', encoding='utf-8')
        manifest['reviewed_site'] = {'site_path': 'original-review/site.json',
                                     'site_sha256': native['site_sha256'],
                                     'review_path': 'original-review/review.json',
                                     'source_root': 'original-review/sources'}
        (self.root / 'saved-sources.json').write_text(json.dumps(manifest), encoding='utf-8')
        (self.root / 'runner.py').write_text('native runner', encoding='utf-8')
        (self.root / 'construction.json').write_text('{}', encoding='utf-8')
        capture_root = self.root / 'capture'
        capture_root.mkdir()
        (capture_root / 'manifest.json').write_text('{}', encoding='utf-8')
        (self.root / 'trace.jsonl').write_text(''.join(json.dumps(
            {'frame': row['frame'], 'time_s': row['time_s']}) + '\n' for row in rows), encoding='utf-8')
        (self.root / 'video_frames.jsonl').write_text(''.join(json.dumps(
            {'carla_frame': row['frame'], 'video_frame': i, 'time_s': row['time_s']}) + '\n'
            for i, row in enumerate(rows)), encoding='utf-8')
        source_paths = [native_path, self.root / 'saved-sources.json',
                        self.root / 'trace.jsonl', self.root / 'video_frames.jsonl',
                        provenance_path, capture_root / 'manifest.json',
                        review_root / 'site.json', review_root / 'review.json',
                        *(source_root / ref['path'] for ref in reviewed['sources'].values()),
                        *(self.root / ref['path'] for ref in media.values())]
        hashes = {path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in source_paths}
        seal = {'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
                'sources': hashes, 'native_revision': {
                    'construction_sha256': hashlib.sha256((self.root / 'construction.json').read_bytes()).hexdigest(),
                    'runner_sha256': hashlib.sha256((self.root / 'runner.py').read_bytes()).hexdigest()}}
        seal_path = self.root / 'capture-seal.json'
        seal_path.write_text(json.dumps(seal), encoding='utf-8')
        verified = delivery.verify_capture_seal(self.root, CASE, manifest, native)
        self.assertEqual(verified['sealed_source_count'], len(hashes))
        seal['sources']['trace.jsonl'] = '0' * 64
        seal_path.write_text(json.dumps(seal), encoding='utf-8')
        with self.assertRaisesRegex(delivery.AuditError, 'sealed source hash changed'):
            delivery.verify_capture_seal(self.root, CASE, manifest, native)
        seal['sources']['trace.jsonl'] = hashes['trace.jsonl']
        seal['events'][-1] = 'restoration_unverified'
        seal_path.write_text(json.dumps(seal), encoding='utf-8')
        with self.assertRaisesRegex(delivery.AuditError, 'lifecycle seal incomplete'):
            delivery.verify_capture_seal(self.root, CASE, manifest, native)
        media["driver_reference"]["sha256"] = "0" * 64
        (self.root / "saved-sources.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "media hash"):
            video.audit(self.root, case_id=CASE, profile=profile)
        with self.assertRaisesRegex(ValueError, "media hash"):
            video._sources.audit_complete(self.root, case_id=CASE, profile=profile)


if __name__ == "__main__":
    unittest.main()
