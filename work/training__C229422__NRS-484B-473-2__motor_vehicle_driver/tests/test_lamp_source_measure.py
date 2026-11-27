import json
import unittest
from lamp_source_measure import ASSIGNMENT, CAMERAS, measure, sha


def fixture(missing=None):
    trace = b''.join((json.dumps({'video_frame':i,'native_frame':1000+i,
        'native_elapsed_s':50+i/20,'ego_speed_mps':0.0,'vehicle_actor_id':7,
        'road_id':1,'headlamp_request':'low'},separators=(',',':'))+'\n').encode()
        for i in range(600))
    mapping = b''.join((json.dumps({'video_frame':i,'native_frame':1000+i,
        'native_elapsed_s':50+i/20},separators=(',',':'))+'\n').encode()
        for i in range(600))
    cameras = {name:sha(name.encode()) for name in CAMERAS}
    review = {'assignment_id':ASSIGNMENT,'source_kind':'synthetic_diagnostic',
        'trace_sha256':sha(trace),'frame_map_sha256':sha(mapping),
        'camera_sha256':cameras,'reviewer_id':'synthetic-test',
        'lawful_parking_source':'synthetic test only','civil_night_source':'synthetic test only',
        'highway_source':'synthetic test only','lawfully_parked':True,
        'highway':True,'civil_night':True,
        'optical_observations':[{'video_frame':i,'source_camera':'overview',
            'pixel_box_xyxy':[1,1,8,8],'lights_displayed':True,
            'depressed_or_dimmed':True,'undepressed_headlamp':False,
            'cowl_or_parking_used':False} for i in range(600)]}
    if missing == 'pixel':review['optical_observations'][200].pop('depressed_or_dimmed')
    if missing == 'clock':review.pop('civil_night_source')
    if missing == 'hash':review['trace_sha256']='0'*64
    if missing == 'frame':review['optical_observations'].pop()
    return trace,mapping,json.dumps(review).encode(),cameras


class SourceMeasurementTest(unittest.TestCase):
    def test_full_interval(self):
        result=measure(*fixture())
        self.assertEqual(result['optical_frame_counts']['depressed_or_dimmed'],600)
        self.assertIsNone(result['legal_conclusion'])
    def test_missing_sources_rejected(self):
        for kind in ('pixel','clock','hash','frame'):
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                measure(*fixture(kind))


if __name__ == '__main__':unittest.main()
