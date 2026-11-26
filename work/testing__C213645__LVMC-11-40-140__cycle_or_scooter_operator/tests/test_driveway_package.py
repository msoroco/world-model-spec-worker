"""Original 900-frame stop, source and controlled-comparison boundaries."""
import unittest

from comparison_audit import AID, PAIRS, audit_pair
from diagnostic_author import site
from driveway_case import CASES, measure_original


class DrivewayPackageTests(unittest.TestCase):
    def test_original_measurement_binds_edge_and_preserves_legal_unknown(self):
        item=CASES[0];packet=site(item);rows=[]
        for i in range(900):
            rows.append({'original_frame':100+i,'time_s':i/20,
                         'source_sha256':'test-source','vehicle_motion_source_sha256':'test-motion',
                         'edge_source_sha256':packet['sidewalk_edge_source_sha256'],
                         'pedestrian_motion_source_sha256':packet['pedestrian_route_source_sha256'],
                         'yield_source_sha256':packet['operator_yield_plan_source_sha256'],
                         'ego_id':'test-cycle','vehicle_type':'bicycle',
                         'speed_mps':0 if 100<=i<=155 else 2,
                         'distance_before_sidewalk_edge_m':2-i/100,
                         'pedestrian_in_conflict_area':190<=i<=210,
                         'pedestrian_actor_ids':['test-pedestrian'],
                         'operator_yield_observed':i==150})
        measured=measure_original(rows,packet,item)
        self.assertEqual(measured['entry_bracket_indices'],[199,200])
        self.assertIsNone(measured['legal_judgment'])
        rows[200]['edge_source_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'edge source changed'):
            measure_original(rows,packet,item)

    def test_comparison_requires_original_accepted_reports(self):
        fixed={'map':'source'}
        def report(suffix,stop,pedestrian,yielded):
            return {'format':'worker-delivery-audit','passed':True,'protocol_fixture_checked':False,
                    'case_id':AID+'__'+suffix,'frame_count':900,'physical_acceptance_claimed':True,
                    'comparison_record':{'source_kind':'original_native_capture',
                                         'fixed_source_sha256':fixed,'camera_plan':['four'],'duration_s':45,
                                         'requested_stop':stop,'requested_pedestrian':pedestrian,
                                         'requested_yield':yielded,
                                         'measurement':{'frame_count':900,
                                                        'last_pre_entry_stop_index':100 if stop else None,
                                                        'pedestrian_conflict_observed':pedestrian,
                                                        'pedestrian_actor_ids':['p'] if pedestrian else [],
                                                        'operator_yield_observed':yielded}}}
        reports={AID+'__stops_pedestrian':report('stops_pedestrian',True,True,True),
                 AID+'__no_stop_pedestrian':report('no_stop_pedestrian',False,True,False),
                 AID+'__stops_no_pedestrian':report('stops_no_pedestrian',True,False,False),
                 AID+'__stops_pedestrian_no_yield':report('stops_pedestrian_no_yield',True,True,False)}
        for name in PAIRS:self.assertTrue(audit_pair(name,reports)['physical_comparison_passed'])
        reports[AID+'__stops_pedestrian']['protocol_fixture_checked']=True
        with self.assertRaisesRegex(ValueError,'original accepted report required'):
            audit_pair('yield_when_needed',reports)


if __name__=='__main__':
    unittest.main()
