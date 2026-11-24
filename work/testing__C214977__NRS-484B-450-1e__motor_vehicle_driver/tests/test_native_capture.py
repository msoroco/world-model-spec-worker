import hashlib
import json
import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from PIL import Image

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
        self.pngs = {}
        for name, size in n.CAMERA_SIZES.items():
            data = BytesIO()
            Image.new('RGB', size, (40, 80, 120)).save(data, format='PNG')
            self.pngs[name] = data.getvalue()
    def tick(self):
        i = self.i
        self.i += 1
        if i == self.fail_at:
            return {'frame': 100 + i + 1, 'time_s': i * .05}
        return {'frame': 100 + i, 'time_s': i * .05}
    def read_subject(self, subject, frame):
        return {'frame': frame, 'case_id': 'case-park-on', 'subject_id': subject,
                'speed_mps': 0, 'halt_activity': 'park',
                'position_m': [2.0, 2.0, 0.0],
                'velocity_mps': [0.0, 0.0, 0.0], 'heading_deg': 0.0,
                'body_vertices_m': [[x, y, z] for x, y in ((1,1),(3,1),(3,3),(1,3)) for z in (0.0,1.0)],
                'body_corners_xy': [[1,1],[3,1],[3,3],[1,3]],
                'crosswalk_id': 'cw', 'marking_status': 'marked',
                'traffic_conflict': False, 'law_direction': False,
                'police_direction': False, 'device_direction': False}
    def read_cameras(self, frame):
        return {name: {'frame': frame, 'source_id': name + '-sensor',
                       'png_bytes': self.pngs[name]} for name in n.CAMERAS}
    def brake(self, subject): self.braked = True
    def cleanup(self): self.cleaned = True


class TestCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        reviews = {name: seal(self.root,name+'.json',{'reviewer':'CPU source fixture','scope':name})
                   for name in ('frontage','highway','camera_pose')}
        self.site = {'cell_id':'C214977','layout':'residence_district','map_name':'Town',
                     'highway_source':'native_map','frontage_source':'survey',
                     'crosswalk_source':'native_map','marking_status_source':'native_map',
                     'signal_governance_source':'native_device','crosswalk_polygon':P,
                     'parking_route':[[-5,2],[2,2]], 'crosswalk_id':'cw', 'marking_status':'marked',
                     'frontage_review_source':reviews['frontage'],
                     'frontage_review_sha256':reviews['frontage']['sha256'],
                     'highway_review_source':reviews['highway'],
                     'highway_review_sha256':reviews['highway']['sha256'],
                     'camera_pose_review_source':reviews['camera_pose'],
                     'camera_pose_review_sha256':reviews['camera_pose']['sha256']}
        self.map_text = '<OpenDRIVE/>'
        self.site['native_opendrive_sha256'] = hashlib.sha256(self.map_text.encode()).hexdigest()
        self.sref = seal(self.root,'site.json',self.site)
        self.vref = seal(self.root,'vehicle.json',{'blueprint':'vehicle.sedan','driver_source':'assigned actor'})
        self.case = {'case_id':'case-park-on','action':'park','exception':'none','destination':'on'}
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
        self.assertEqual(verified['decoded_original_pngs'],3600)
        self.assertTrue(verified['actual_pixels'])
        self.assertFalse(verified['full_video_decode'])
        comparison_source = s.comparison_source(receipt_ref,self.root,self.root/'out',self.case,verified)
        self.assertEqual(comparison_source['site_source_sha256'],self.sref['sha256'])
        self.assertEqual(comparison_source['vehicle_source_sha256'],self.vref['sha256'])
        self.assertEqual(comparison_source['original_frame_count'],900)
        self.assertFalse(comparison_source['delivery_accepted'])
        self.assertFalse(any(comparison_source['exception_sources'].values()))
        (self.root/'out'/'site.json').write_bytes((self.root/'site.json').read_bytes())
        (self.root/'out'/'vehicle.json').write_bytes((self.root/'vehicle.json').read_bytes())
        for name in ('frontage','highway','camera_pose'):
            (self.root/'out'/(name+'.json')).write_bytes((self.root/(name+'.json')).read_bytes())
        derived = s.prepare_analysis_sources(self.root/'out',self.case)
        self.assertEqual(derived['verified']['decoded_original_pngs'],3600)
        self.assertEqual(len((self.root/'out'/'crosswalk-rows.jsonl').read_text().splitlines()),900)
        with self.assertRaisesRegex(n.SourceError,'derived source output collision'):
            s.prepare_analysis_sources(self.root/'out',self.case)
        with self.assertRaisesRegex(n.SourceError, 'measured destination mismatch'):
            s.comparison_source(receipt_ref,self.root,self.root/'out',
                                {**self.case,'destination':'off'},verified)
    def test_camera_png_tamper_rejected(self):
        a = Adapter()
        n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out')
        receipt_ref = {'path':'native-receipt.json', 'sha256':hashlib.sha256((self.root/'out'/'native-receipt.json').read_bytes()).hexdigest()}
        (self.root/'out'/'camera-sources'/'overview'/'0000.png').write_bytes(b'bad')
        with self.assertRaisesRegex(n.SourceError,'camera PNG hash mismatch'):
            s.verify(receipt_ref,self.root,self.root/'out',self.case)

    def test_full_native_projection_and_seal(self):
        from native_output_bridge import seal_original_capture
        out = self.root/'out'
        n.capture(Adapter(),self.sref,self.vref,self.case,self.root,out)
        for name in ('site','vehicle','frontage','highway','camera_pose'):
            (out/(name+'.json')).write_bytes((self.root/(name+'.json')).read_bytes())
        (out/'carla_recorder.log').write_text('synthetic recorder fixture\n')
        (out/'construction.json').write_text(json.dumps({'case_id':self.case['case_id']})+'\n')
        (out/'runner.py').write_text('# CPU fixture entrypoint\n')
        (out/'config.json').write_text(json.dumps({'case':self.case})+'\n')
        seal = seal_original_capture(out,self.case,self.map_text,restoration_verified=True)
        self.assertTrue(seal.is_file())
        for name in ('trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
                     'capture/native/frames.jsonl','overview.mkv','approach.mkv',
                     'reference_corner.mkv','driver_reference.mkv'):
            self.assertTrue((out/name).is_file(),name)
        self.assertEqual(len((out/'capture/native/frames.jsonl').read_text().splitlines()),900)
        self.assertFalse(json.loads(seal.read_text())['physical_acceptance_claimed'])
    def test_missing_camera_pixels_rejected(self):
        a = Adapter()
        a.pngs['overview'] = b''
        with self.assertRaisesRegex(n.SourceError,'Native camera PNG pixels missing'):
            n.capture(a,self.sref,self.vref,self.case,self.root,self.root/'out')
        self.assertTrue(a.braked and a.cleaned)
        self.assertFalse((self.root/'out'/'native-receipt.json').exists())
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
    def test_exception_requires_matching_sealed_packet(self):
        a = Adapter()
        case = {**self.case, 'exception':'police_direction'}
        with self.assertRaisesRegex(n.SourceError,'exact exception source missing'):
            n.capture(a,self.sref,self.vref,case,self.root,self.root/'out')
        packet = seal(self.root,'exception.json',{'kind':'device_direction'})
        with self.assertRaisesRegex(n.SourceError,'kind differs'):
            n.capture(a,self.sref,self.vref,case,self.root,self.root/'out',exception_ref=packet)
        self.assertEqual(a.i,0)


if __name__ == '__main__': unittest.main()
