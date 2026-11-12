import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
SPEC = importlib.util.spec_from_file_location('truck_delivery_audit',FOLDER/'delivery_audit.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class PixelAuditTest(unittest.TestCase):
    def test_reviewed_pixels_and_black_rejection(self):
        from collections import namedtuple
        Frame = namedtuple('Frame','index width height pixels')
        sample = [{'video_frame':0,'bbox_xyxy':[0,0,4,4]}]
        check, finish = AUDIT.pixel_checker(sample,4,4)
        check(Frame(0,4,4,b'\0\0\0'*8+b'\xff\0\0'*8))
        finish()
        check, _ = AUDIT.pixel_checker(sample,4,4)
        with self.assertRaisesRegex(ValueError,'no visible pixel detail'):
            check(Frame(0,4,4,b'\0'*48))
        check, finish = AUDIT.pixel_checker([{'video_frame':1,'bbox_xyxy':[0,0,4,4]}],4,4)
        check(Frame(0,4,4,b'\0\0\0'*8+b'\xff\0\0'*8))
        with self.assertRaisesRegex(ValueError,'was not decoded'):
            finish()

    def test_media_decode_runs_reviewed_pixel_checker(self):
        media = AUDIT.media_module()
        with tempfile.TemporaryDirectory(prefix='truck-pixel-audit-') as temp:
            path = Path(temp)/'pixels.mkv'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                            '-f','lavfi','-i','testsrc=size=8x8:rate=20',
                            '-frames:v','2','-c:v','ffv1',str(path)],check=True)
            check, finish = AUDIT.pixel_checker(
                [{'video_frame':0,'bbox_xyxy':[0,0,8,8]},
                 {'video_frame':1,'bbox_xyxy':[0,0,8,8]}],8,8)
            result = media.audit(path,2,
                    checkers={'reviewed_actor_pixels':(AUDIT.digest(FOLDER/'delivery_audit.py'),check)})
            finish()
            self.assertEqual(result['frames'],2)
            self.assertEqual(result['checks']['frame_count'],'all-decoded-frames')

    def test_fixture_rejected_before_delivery_receipt(self):
        root = REPO/'.runtime-work/c149237-gap_below_500ft-saved-v14/v0001/analysis'
        if not root.is_dir():
            self.skipTest('retained diagnostic attempt not present')
        with tempfile.TemporaryDirectory(prefix='truck-delivery-reject-') as temp:
            with self.assertRaisesRegex(ValueError,'frame count differs from planned capture'):
                AUDIT.require_native_delivery(
                    root,FOLDER.name+'__gap_below_500ft','fixture-job',1,'fixture-recording',
                    Path(temp)/'review.json',root/'delivery-audit.json',
                    Path(temp)/'decode.json')


if __name__ == '__main__':
    unittest.main()
