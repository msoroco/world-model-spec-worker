import unittest
from test_safety_zone import scene
from safety_zone import CASES, THIRTY_FT_M, measure_original

class OriginalMeasurementTests(unittest.TestCase):
    def test_900_frame_original_shape_and_corrupt_station(self):
        case=next(c for c in CASES if c.case_id=='west_end_at_30ft')
        s=scene(case)
        station=case.offset_m
        row={'vehicle_id':'ego-101','traffic_id':'traffic-202',
             'activity':case.activity,'exception':case.exception,
             'vehicle_body_rect_m':s['target_body_rect_m'],
             'signed_end_station_m':station,'between_zone_curb':False,
             'vehicle_speed_mps':0.0,'traffic_speed_mps':4.0}
        for name in ('frame','vehicle_motion','vehicle_body','zone','curb',
                     'activity','exception','traffic_motion'):
            row[name+'_source_sha256']=s.get(name+'_source_sha256','test-source-'+name)
        rows=[dict(row,original_frame=1000+i,time_s=i/20) for i in range(900)]
        measured=measure_original(rows,s,case)
        self.assertEqual(measured['frame_count'],900)
        self.assertAlmostEqual(measured['terminal_signed_end_station_m'],THIRTY_FT_M)
        rows[450]['signed_end_station_m']+=.2
        with self.assertRaisesRegex(ValueError,'station differs'):
            measure_original(rows,s,case)
