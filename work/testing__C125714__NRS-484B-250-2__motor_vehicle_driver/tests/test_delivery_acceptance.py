"""CPU checks of independent acceptance boundaries, without a Native claim."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
from delivery_acceptance import pixel_checker, verify_physical, verify_seal  # noqa: E402
from worker_exchange.common import sha  # noqa: E402
from worker_exchange.media import Frame  # noqa: E402


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


class DeliveryAcceptanceBoundaries(unittest.TestCase):
    def test_seal_and_closure_reject_removed_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            names = ('config.json', 'crossing_history.jsonl', 'road_geometry.json',
                     'video_frames.jsonl', 'controller_history.jsonl', 'trace.jsonl',
                     'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                     'driver_reference.mkv')
            for name in names:
                (root / name).write_text('diagnostic source\n')
            write(root / 'capture-seal.json', {
                'format': 'worker-sealed-capture', 'provenance_kind': 'synthetic_fixture',
                'diagnostic_fixture': True,
                'sources': {name: sha(root / name) for name in names}})
            write(root / 'native-exit.json', {
                'event': 'native_exit',
                'capture_seal_sha256': sha(root / 'capture-seal.json')})
            write(root / 'owner-release.json', {
                'event': 'owner_released', 'operator_attested': True,
                'native_exit_sha256': sha(root / 'native-exit.json')})
            self.assertEqual(verify_seal(root, diagnostic=True)['diagnostic_fixture'], True)
            with self.assertRaisesRegex(ValueError, 'provenance'):
                verify_seal(root, diagnostic=False)
            (root / 'controller_history.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Sealed original source changed'):
                verify_seal(root, diagnostic=True)

    def test_physical_outcome_requires_bound_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'trace.jsonl').write_text('{}\n')
            check = {'status': 'met', 'method': 'source body motion',
                     'sources': {'trace.jsonl': sha(root / 'trace.jsonl')}}
            result = {'physical_acceptance_claimed': False,
                      'maneuver_completed': True,
                      'physical_checks': {'setup': check, 'maneuver': check}}
            verify_physical(result, root)
            (root / 'trace.jsonl').write_text('{"changed":true}\n')
            with self.assertRaisesRegex(ValueError, 'Physical completion source changed'):
                verify_physical(result, root)

    def test_reviewed_pixel_roi_must_have_detail(self):
        sample = [{'video_frame': 0, 'actor_id': 4, 'bbox_xyxy': [0, 0, 4, 4]}]
        check, finish = pixel_checker(sample, 4, 4)
        pixels = bytearray(b'\x00\x00\x00' * 16)
        with self.assertRaisesRegex(ValueError, 'no visible pixel detail'):
            check(Frame(0, 4, 4, bytes(pixels)))
        pixels[0:3] = b'\xff\x00\x00'
        check(Frame(0, 4, 4, bytes(pixels)))
        finish()


if __name__ == '__main__':
    unittest.main()
