"""The production attestation rejects absent or stale independent source review."""
import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

ASSIGNMENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSIGNMENT))
import production_delivery_audit as production
from production_delivery_audit import VIEWS, independent_review, sealed_sources


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProductionReviewTest(unittest.TestCase):
    def setUp(self):
        scratch = ASSIGNMENT.parents[1] / '.runtime-work' / 'c111125-2a-owner'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        frame = self.root / 'original-frame-map.json'
        frame.write_text(json.dumps([{'frame': 11}, {'frame': 12}]) + '\n')
        self.packet = {'frame_map_ref': {'path': frame.name, 'sha256': sha(frame)},
                       'event_ref': {'sha256': 'events'},
                       'camera_media_refs': {view: {'sha256': 'video-' + view}
                                             for view in VIEWS}}
        self.joined = {'overview': {'0': 'rgb'}}
        self.review = {'case_id': 'case', 'reviewer_id': 'reviewer-1',
                       'reviewer_role': 'independent_source_reviewer',
                       'method': 'manual_original_frame_and_event_review',
                       'source_bindings': {
                           'capture_seal_sha256': 'seal',
                           'saved_result_sha256': 'result',
                           'source_frame_samples_sha256': 'samples',
                           'original_events_sha256': 'events',
                           'original_frame_map_sha256': sha(frame),
                           'camera_media_sha256': {view: 'video-' + view
                                                   for view in VIEWS}},
                       'sample_rgb_sha256': self.joined,
                       'observations': {name: {'status': 'met',
                           'explanation': 'Reviewed original event and visible source frame.',
                           'original_frame_ids': [11]}
                           for name in ('official_circular_green_visible',
                                        'other_user_context_reviewed',
                                        'ego_yield_reviewed',
                                        'physical_completion_reviewed',
                                        'all_four_views_reviewed')},
                       'legal_verdict_claimed': False}

    def check(self):
        return independent_review(self.root, 'case', 'seal', 'result',
                                  'samples', self.joined, self.packet)

    def write_review(self):
        (self.root / 'independent-source-review.json').write_text(
            json.dumps(self.review) + '\n')

    def test_missing_review_fails_closed(self):
        with self.assertRaises(FileNotFoundError):
            self.check()

    def test_bound_review_passes(self):
        self.write_review()
        self.assertEqual(self.check()['path'], 'independent-source-review.json')

    def test_stale_result_rejected(self):
        self.review['source_bindings']['saved_result_sha256'] = 'stale'
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'source binding stale'):
            self.check()

    def test_unreviewed_physical_completion_rejected(self):
        self.review['observations']['physical_completion_reviewed']['status'] = 'unverified'
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'physical_completion_reviewed'):
            self.check()

    def test_nonoriginal_frame_rejected(self):
        self.review['observations']['ego_yield_reviewed']['original_frame_ids'] = [999]
        self.write_review()
        with self.assertRaisesRegex(ValueError, 'ego_yield_reviewed'):
            self.check()

    def make_seal(self):
        names = ('original-green-packet.json', 'original-events.json',
                 'site.json', 'trace.jsonl', 'video_frames.jsonl',
                 'runner.py', 'construction.json', 'source-frame-samples.json')
        for name in names:
            (self.root / name).write_text(name + '\n')
        for view in VIEWS:
            (self.root / (view + '.mkv')).write_bytes(view.encode())
        acquisition = {name: {'kind': 'original_native',
                              'sha256': sha(self.root / name)}
                       for name in ('original-green-packet.json', 'site.json',
                                    'original-events.json', 'video_frames.jsonl')}
        (self.root / 'acquisition.json').write_text(json.dumps(acquisition) + '\n')
        packet = {'case_id': 'case',
                  'event_ref': {'path': 'original-events.json',
                                'sha256': sha(self.root / 'original-events.json')},
                  'frame_map_ref': self.packet['frame_map_ref'],
                  'camera_media_refs': {view: {'path': view + '.mkv',
                      'sha256': sha(self.root / (view + '.mkv'))} for view in VIEWS}}
        media = {'case_id': 'case', 'event_ref': packet['event_ref'],
                 'frame_map_ref': packet['frame_map_ref'],
                 'camera_media_refs': packet['camera_media_refs'],
                 'camera_capture_complete': True,
                 'software_audit_passed': True}
        (self.root / 'media-capture-receipt.json').write_text(json.dumps(media) + '\n')
        sources = {path.name: sha(path) for path in self.root.iterdir()
                   if path.is_file()}
        seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'native',
                'diagnostic_fixture': False, 'frames': 900,
                'restoration': {'restored': True},
                'events': ['capture_finished', 'encoders_closed',
                           'restoration_verified'],
                'encoder_exit_codes': {view: 0 for view in VIEWS},
                'sources': sources,
                'source_digest': hashlib.sha256(json.dumps(sources,
                    sort_keys=True, separators=(',', ':'),
                    ensure_ascii=False).encode()).hexdigest(),
                'native_revision': {'runner_sha256': sources['runner.py'],
                                    'construction_sha256': sources['construction.json']}}
        (self.root / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
        return packet, seal

    def test_capture_lifecycle_and_media_sources_bound(self):
        packet, _ = self.make_seal()
        self.assertEqual(sealed_sources(self.root, packet)[0]['frames'], 900)
        (self.root / 'overview.mkv').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            sealed_sources(self.root, packet)

    def test_missing_restoration_rejected(self):
        packet, seal = self.make_seal()
        seal['restoration'] = {'restored': False}
        (self.root / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
        with self.assertRaisesRegex(ValueError, 'lifecycle'):
            sealed_sources(self.root, packet)

    def test_original_png_video_pixel_join_and_tamper(self):
        video = self.root / 'overview.mkv'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                        'color=c=blue:s=16x16:r=20', '-frames:v', '900',
                        '-c:v', 'ffv1', str(video)], check=True,
                       capture_output=True)
        folder = self.root / 'source-frame-samples'
        folder.mkdir()
        refs = {}
        for index in (0, 450, 899):
            raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video),
                '-vf', f'select=eq(n\\,{index})', '-vsync', '0',
                '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                check=True, capture_output=True).stdout
            path = folder / f'overview-{index:06d}.png'
            Image.frombytes('RGB', (16, 16), raw).save(path)
            refs[str(index)] = {'path': str(path.relative_to(self.root)),
                                'sha256': sha(path)}
        manifest = {'case_id': 'case', 'samples': {'overview': refs}}
        (self.root / 'source-frame-samples.json').write_text(json.dumps(manifest) + '\n')
        packet = {'case_id': 'case', 'camera_media_refs': {
            'overview': {'path': video.name, 'sha256': sha(video)}}}
        with mock.patch.object(production, 'VIEWS', ('overview',)), mock.patch.object(
                production, 'PRODUCTION_PROFILE', {'overview': (16, 16)}):
            self.assertEqual(len(production.sampled_pixel_joins(self.root, packet)[1]['overview']), 3)
            path = folder / 'overview-000450.png'
            Image.new('RGB', (16, 16), 'red').save(path)
            manifest['samples']['overview']['450']['sha256'] = sha(path)
            (self.root / 'source-frame-samples.json').write_text(json.dumps(manifest) + '\n')
            with self.assertRaisesRegex(ValueError, 'pixel join differs'):
                production.sampled_pixel_joins(self.root, packet)


if __name__ == '__main__':
    unittest.main()
