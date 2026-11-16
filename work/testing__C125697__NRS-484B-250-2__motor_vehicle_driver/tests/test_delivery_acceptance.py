"""Independent acceptance boundary proofs; synthetic fixtures never pass delivery."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from delivery_acceptance import pixel_checker, verify_physical, verify_review, verify_seal  # noqa: E402
import delivery_acceptance  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.media import Frame  # noqa: E402


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


class DeliveryAcceptanceBoundaries(unittest.TestCase):
    def test_seal_closure_and_missing_original_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'capture').mkdir()
            names = ('config.json', 'junction_context.json', 'crossing_history.jsonl',
                     'controller_history.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                     'capture/evidence.jsonl', 'overview.mkv', 'approach.mkv',
                     'reference_corner.mkv', 'driver_reference.mkv')
            for name in names:
                (root / name).write_text('synthetic diagnostic source\n')
            seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'native',
                    'diagnostic_fixture': True, 'frames': 1,
                    'restoration': {'restored': True}, 'encoder_exit_codes': {'fixture': 0},
                    'native_revision': {'construction_sha256': 'fixture', 'runner_sha256': 'fixture'},
                    'sources': {name: sha(root / name) for name in names}}
            write(root / 'capture-seal.json', seal)
            write(root / 'native-exit.json', {
                'event': 'native_exit', 'native_revision': seal['native_revision'],
                'capture_seal_sha256': sha(root / 'capture-seal.json')})
            write(root / 'owner-release.json', {
                'event': 'owner_released', 'operator_attested': True,
                'native_exit_sha256': sha(root / 'native-exit.json')})
            self.assertTrue(verify_seal(root, diagnostic=True)['diagnostic_fixture'])
            with self.assertRaisesRegex(ValueError, 'provenance'):
                verify_seal(root, diagnostic=False)
            (root / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Sealed original source changed'):
                verify_seal(root, diagnostic=True)

    def test_physical_completion_requires_live_source_hashes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'crossing_history.jsonl').write_text('{}\n')
            check = {'status': 'met', 'method': 'original complete-body clearance',
                     'sources': {'crossing_history.jsonl': sha(root / 'crossing_history.jsonl')}}
            result = {'physical_acceptance_claimed': False,
                      'setup_confirmed': True, 'behavior_attempted': True,
                      'maneuver_completed': True,
                      'physical_checks': {'setup': check, 'target': check,
                                          'maneuver': check}}
            verify_physical(result, root)
            (root / 'crossing_history.jsonl').write_text('{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'Physical completion source changed'):
                verify_physical(result, root)

    def test_actor_roi_rejects_blank_pixels(self):
        sample = [{'video_frame': 0, 'actor_id': 17, 'bbox_xyxy': [0, 0, 4, 4]}]
        check, finish = pixel_checker(sample, 4, 4)
        pixels = bytearray(b'\x00\x00\x00' * 16)
        with self.assertRaisesRegex(ValueError, 'no visible pixel detail'):
            check(Frame(0, 4, 4, bytes(pixels)))
        pixels[0:3] = b'\xff\x00\x00'
        check(Frame(0, 4, 4, bytes(pixels)))
        finish()

    def test_pixel_review_joins_all_original_actor_ids_and_rejects_stale_map(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":7,"time_s":0}\n')
            (root / 'crossing_history.jsonl').write_text(
                '{"frame":7,"ego":{"actor_id":11},"other":{"actor_id":12}}\n')
            for name in delivery_acceptance.CAMERAS:
                (root / (name + '.mkv')).write_bytes(b'diagnostic source')
            observations = [
                {'video_frame': 0, 'actor': role, 'actor_id': actor_id,
                 'camera': name, 'bbox_xyxy': [0, 0, 4, 4]}
                for name in delivery_acceptance.CAMERAS
                for role, actor_id in (('ego', 11), ('other', 12))]
            review = {'case_id': 'case', 'reviewer': 'CPU fixture reviewer',
                      'method': 'reviewed original frame and actor identity',
                      'frame_map_sha256': sha(root / 'video_frames.jsonl'),
                      'source_sha256': {name: sha(root / (name + '.mkv'))
                                        for name in delivery_acceptance.CAMERAS},
                      'observations': observations}
            review_path = root / 'pixel-review.json'
            write(review_path, review)

            def decoded(_video, _frames, *, checkers, mapping_sha256):
                self.assertEqual(mapping_sha256, sha(root / 'video_frames.jsonl'))
                pixels = bytearray(b'\x00\x00\x00' * 16)
                pixels[0:3] = b'\xff\x00\x00'
                for _, callback in checkers.values():
                    callback(Frame(0, 4, 4, bytes(pixels)))
                return {'passed': True}

            with patch.dict(delivery_acceptance.CAMERAS,
                            {name: (4, 4) for name in delivery_acceptance.CAMERAS}):
                with patch.object(delivery_acceptance.media, 'audit', side_effect=decoded):
                    self.assertEqual(verify_review(root, 'case', review_path, 1), sha(review_path))
                    review['frame_map_sha256'] = '0' * 64
                    write(review_path, review)
                    with self.assertRaisesRegex(ValueError, 'missing or stale'):
                        verify_review(root, 'case', review_path, 1)


if __name__ == '__main__':
    unittest.main()
