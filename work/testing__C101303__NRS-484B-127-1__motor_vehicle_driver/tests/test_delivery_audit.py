import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
SPEC = importlib.util.spec_from_file_location('c101303_delivery_audit', FOLDER/'delivery_audit.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
from worker_exchange.media import Frame, audit as decode_video


class DeliveryAuditTest(unittest.TestCase):
    def test_source_join_and_missing_participant_rejection(self):
        root = REPO/'.runtime-work/c101303-final-v3/base-primary-compat'
        case = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
        joined = audit.validate_join(root/'video_frames.jsonl', root/'vehicle_history.jsonl',
                                     root/'trace.jsonl', case, expected_frames=9)
        self.assertEqual(joined['participant_ids'], [205, 307])
        self.assertEqual(joined['frames'], 9)
        queued = REPO/'.runtime-work/c101303-queued-participant-v2/primary-compat'
        queued_case = case.replace('source_verified_base','source_verified_queued_traffic')
        queued_join = audit.validate_join(queued/'video_frames.jsonl',
                                         queued/'vehicle_history.jsonl',queued/'trace.jsonl',
                                         queued_case,expected_frames=9)
        self.assertEqual(queued_join['participant_ids'], [205,307,411])
        with tempfile.TemporaryDirectory() as tmp:
            incomplete = Path(tmp)/'vehicle_history.jsonl'
            rows = [json.loads(line) for line in (root/'vehicle_history.jsonl').read_text().splitlines()]
            for row in rows:
                row['traffic_actor_ids'].append(411)
            incomplete.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Missing complete participant bodies'):
                audit.validate_join(root/'video_frames.jsonl', incomplete, root/'trace.jsonl',
                                    case, expected_frames=9)
            with self.assertRaisesRegex(ValueError, 'Missing original source'):
                audit.validate_join(root/'video_frames.jsonl', Path(tmp)/'missing.jsonl',
                                    root/'trace.jsonl', case, expected_frames=9)

    def test_reviewed_pixels_and_black_rejection(self):
        observation = [{'video_frame':0,'bbox_xyxy':[0,0,4,4]}]
        inspect, finish = audit.pixel_checker(observation,width=4,height=4)
        pixels = b'\x00\x00\x00'*8+b'\xff\x00\x00'*8
        inspect(Frame(0,4,4,pixels))
        finish()
        inspect, _ = audit.pixel_checker(observation,width=4,height=4)
        with self.assertRaisesRegex(ValueError, 'no visible pixel detail'):
            inspect(Frame(0,4,4,b'\x00'*48))

    def test_full_video_decode_applies_pixel_checker(self):
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp)/'pixels.mkv'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi',
                            '-i','testsrc=size=8x8:rate=20','-frames:v','2','-c:v','ffv1',
                            str(video)],check=True)
            inspect, finish = audit.pixel_checker(
                [{'video_frame':0,'bbox_xyxy':[0,0,8,8]},
                 {'video_frame':1,'bbox_xyxy':[0,0,8,8]}],width=8,height=8)
            receipt = decode_video(video,2,checkers={'actor_roi':(audit.sha(FOLDER/'delivery_audit.py'),inspect)})
            finish()
            self.assertEqual(receipt['frames'],2)
            self.assertEqual(receipt['checks']['frame_count'],'all-decoded-frames')

    def test_diagnostic_attempt_never_claims_delivery(self):
        root = REPO/'.runtime-work/c101303-final-v3/base-primary-compat'
        case = 'testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_base'
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Native non-diagnostic result required'):
                audit.audit_attempt(root,case,'fixture-job',1,'fixture-recording',
                                    Path(tmp)/'review.json',Path(tmp)/'audit.json',
                                    Path(tmp)/'decode.json')


if __name__ == '__main__':
    unittest.main()
