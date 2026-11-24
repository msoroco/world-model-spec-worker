import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fallback_triggers import evaluate


def row(time, x, y, heading=(1, 0), error=0):
    return {'time_s': time, 'native_center_xy_m': [x, y],
            'native_forward_xy': list(heading), 'controller_request': {'route_error_m': error},
            'native_body_xy_m': [[x-1.1,y-2.6],[x+1.1,y-2.6],
                                 [x+1.1,y+2.6],[x-1.1,y+2.6]]}


class FallbackTriggerTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.samples = root/'native_samples.jsonl'
        self.geometry = root/'road_geometry.json'
        self.audit = root/'pixel_audit.jsonl'
        self.video = root/'reference_corner.mkv'
        self.video.write_bytes(b'synthetic pixel fixture; no Native image')
        self.geometry.write_text(json.dumps({'native_map_sha256':'a'*64,
            'road_directions_native':{'approach_forward':[1,0],
              'approach_opposing':[-1,0],'destination_forward':[0,-1],
              'destination_opposing':[0,1]},
            'destination_right_normal_native':[1,0],
            'destination_centerline_point_native_m':[0,0],
            'intersection_entry_point_native_m':[-7,0],
            'destination_exit_point_native_m':[0,-7]}))

    def motion(self, *, complete=True, error=.1):
        rows = [row(.05,-20,1.75),row(.10,1.75,-5,(0,-1),error)]
        rows += [row(.05*(i+1),1.75,-11 if complete else -5,(0,-1),error)
                 for i in range(2,480)]
        self.samples.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')

    def pixels(self, visible):
        digest=hashlib.sha256(self.video.read_bytes()).hexdigest()
        self.audit.write_text('\n'.join(json.dumps({'video_frame':i,
            'source_video_sha256':digest,'body_visible':i<visible,
            'centerline_visible':True}) for i in range(20))+'\n')

    def test_completion_trigger_positive_and_negative(self):
        for complete,triggered in ((False,True),(True,False)):
            self.motion(complete=complete)
            result=evaluate('fallback1',samples_path=self.samples,geometry_path=self.geometry)
            self.assertEqual(result['triggered'],triggered)
            self.assertEqual(result['source_sha256']['native_samples.jsonl'],
                             hashlib.sha256(self.samples.read_bytes()).hexdigest())

    def test_tracking_trigger_positive_and_negative(self):
        for error,triggered in ((.36,True),(.35,False)):
            self.motion(error=error)
            result=evaluate('fallback2',samples_path=self.samples,geometry_path=self.geometry,
                            requested_exit_x_m=1.75)
            self.assertEqual(result['triggered'],triggered)
            self.assertEqual(result['measured_value'],error)

    def test_framing_trigger_positive_and_negative(self):
        for visible,triggered in ((18,True),(19,False)):
            self.pixels(visible)
            result=evaluate('fallback3',pixel_audit_path=self.audit,video_path=self.video)
            self.assertEqual(result['triggered'],triggered)
            self.assertEqual(result['source_sha256'][self.video.name],
                             hashlib.sha256(self.video.read_bytes()).hexdigest())

    def test_unbound_pixel_audit_rejected(self):
        self.pixels(20);self.video.write_bytes(b'changed source')
        with self.assertRaisesRegex(ValueError,'not bound'):
            evaluate('fallback3',pixel_audit_path=self.audit,video_path=self.video)


if __name__=='__main__': unittest.main()
