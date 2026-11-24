import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture as n
import saved_crosswalk as s
from test_crosswalk import Fake, P


def seal(root, name, obj):
    raw = json.dumps(obj).encode()
    (root / name).write_bytes(raw)
    return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}


class Adapter(Fake):
    def __init__(self, fail_at=None):
        super().__init__()
        self.i = 0
        self.fail_at = fail_at
        self.braked = False
        self.cleaned = False
    def tick(self):
        i = self.i
        self.i += 1
        if i == self.fail_at:
            return {'frame': 100 + i + 1, 'time_s': i * .05}
        return {'frame': 100 + i, 'time_s': i * .05}
    def read_subject(self, subject, frame):
        return {'frame': frame, 'case_id': 'case-park-on', 'subject_id': subject,
                'speed_mps': 0, 'halt_activity': 'park',
                'body_corners_xy': [[1,1],[3,1],[3,3],[1,3]],
                'crosswalk_id': 'cw', 'marking_status': 'marked',
                'traffic_conflict': False, 'law_direction': False,
                'police_direction': False, 'device_direction': False}
    def read_cameras(self, frame):
        return {name: {'frame': frame, 'source_id': name + '-sensor'} for name in n.CAMERAS}
    def brake(self, subject): self.braked = True
    def cleanup(self): self.cleaned = True


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.site = {'cell_id':'C214977','layout':'residence_district','map_name':'Town',
                     'highway_source':'native_map','frontage_source':'survey',
                     'crosswalk_source':'native_map','marking_status_source':'native_map',
                     'signal_governance_source':'native_device','crosswalk_polygon':P,
                     'parking_route':[[-5,2],[2,2]], 'crosswalk_id':'cw', 'marking_status':'marked'}
        self.sref = seal(self.root,'site.json',self.site)
        self.vref = seal(self.root,'vehicle.json',{'blueprint':'vehicle.sedan','driver_source':'assigned actor'})
        self.case = {'case_id':'case-park-on','action':'park','exception':'none','destination':[2,2]}
    def tearDown(self): self.tmp.cleanup()
    def test_full_capture(self):
        a = Adapter()
        receipt = n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out')
        self.assertEqual(receipt['measurement']['halt_contained_crosswalk_frames'],900)
        self.assertEqual(receipt['frame_count'],900)
        self.assertTrue(a.braked and a.cleaned)
        for ref in receipt['sources'].values():
            self.assertEqual(hashlib.sha256((self.root/'out'/ref['path']).read_bytes()).hexdigest(),ref['sha256'])
        receipt_ref = {'path':'native-receipt.json', 'sha256':hashlib.sha256((self.root/'out'/'native-receipt.json').read_bytes()).hexdigest()}
        verified = s.verify(receipt_ref,self.root,self.root/'out',self.case)
        self.assertTrue(verified['source_verified'])
        self.assertFalse(verified['actual_pixels'])
    def test_saved_tamper_rejected(self):
        a = Adapter()
        n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out')
        receipt_ref = {'path':'native-receipt.json', 'sha256':hashlib.sha256((self.root/'out'/'native-receipt.json').read_bytes()).hexdigest()}
        (self.root/'out'/'actor-rows.json').write_text('[]')
        with self.assertRaisesRegex(n.SourceError,'source hash mismatch'):
            s.verify(receipt_ref,self.root,self.root/'out',self.case)
    def test_gap_brakes_and_does_not_write_receipt(self):
        a = Adapter(fail_at=10)
        with self.assertRaisesRegex(n.SourceError,'frame gap'):
            n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out')
        self.assertTrue(a.braked and a.cleaned)
        self.assertFalse((self.root/'out'/'native-receipt.json').exists())
    def test_profile_rejects_shortened_capture(self):
        a = Adapter()
        with self.assertRaisesRegex(n.SourceError,'900 frames'):
            n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out',20)
        self.assertEqual(a.i,0)


if __name__ == '__main__': unittest.main()
