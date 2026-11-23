import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assigned_crosswalk', ROOT / 'crosswalk.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def site_packet():
    return {'source': 'original_native_map', 'map_name': 'SourceTown',
            'intersection_id': 'I-17',
            'highway_context': {'source': 'original_map_and_local_review'},
            'crosswalk': {'source': 'original_map_marking',
                          'polygon_xy_m': [[-2,-1],[2,-1],[2,5],[-2,5]]},
            'ego_turn': {'direction': 'left', 'connected': True,
                         'waypoints': [[-8,-4],[-2,-2],[0,0],[0,8]],
                         'destination_lane_ids': ['north_1', 'north_2']},
            'lanes': [
                {'lane_id':'north_1','direction':'north','type':'driving','polygon_xy_m':[[-2,0],[0,0],[0,9],[-2,9]]},
                {'lane_id':'north_2','direction':'north','type':'driving','polygon_xy_m':[[0,0],[2,0],[2,9],[0,9]]},
                {'lane_id':'south_1','direction':'south','type':'driving','polygon_xy_m':[[2,0],[4,0],[4,9],[2,9]]}],
            'official_devices': {'inventory_source':'original_map_and_actor_scan',
                                 'coverage':'all_relevant_approaches','entries':[]}}


class CrosswalkTest(unittest.TestCase):
    def test_destination_half_uses_every_designated_lane(self):
        packet = site_packet()
        site = m.bind_site(packet, 'SourceTown', 'left')
        self.assertEqual(len(site['destination_half']), 2)
        self.assertTrue(m.polygon_contains([2,3], site['crosswalk_polygon']))
        self.assertFalse(m.polygon_contains([3,3], site['destination_half'][0]))
        packet['ego_turn']['destination_lane_ids'] = ['north_1']
        with self.assertRaisesRegex(m.SourceError, 'omits'):
            m.bind_site(packet, 'SourceTown', 'left')

    def test_source_gate_rejects_missing_crosswalk_and_device_inventory(self):
        packet = site_packet()
        packet['crosswalk']['source'] = 'authored_label'
        with self.assertRaisesRegex(m.SourceError, 'crosswalk classification'):
            m.bind_site(packet, 'SourceTown', 'left')
        packet = site_packet()
        packet['official_devices']['coverage'] = 'ego_only'
        with self.assertRaisesRegex(m.SourceError, 'inventory incomplete'):
            m.bind_site(packet, 'SourceTown', 'left')

    def test_original_frame_and_participant_binding(self):
        site = m.bind_site(site_packet(), 'SourceTown', 'left')
        ego = {'frame':20,'source_ref':'native/ego.jsonl#20','actor_id':1,
               'classification':'motor_vehicle_driver','body_center_xy_m':[0,-2],'brake':True}
        pedestrian = {'frame':20,'source_ref':'native/person.jsonl#20','actor_id':2,
                      'classification':'pedestrian','body_center_xy_m':[1,2]}
        review = {'source_refs':['legal/exception-review.json'],'status':'none_identified'}
        found = m.measure_frame(site,20,ego,pedestrian,review)
        self.assertTrue(found['pedestrian_in_crosswalk'])
        self.assertTrue(found['pedestrian_on_destination_half'])
        self.assertEqual(found['device_condition'],'absent')
        self.assertTrue(found['ego_brake'])
        pedestrian['frame'] = 21
        with self.assertRaisesRegex(m.SourceError, 'join mismatch'):
            m.measure_frame(site,20,ego,pedestrian,review)

    def test_operating_device_rejects_unverified_state(self):
        packet = site_packet()
        packet['official_devices']['entries'] = [{'official':True,'relevant':True,
            'source_ref':'native/signal.jsonl','state_by_frame':{'20':'operating'}}]
        site = m.bind_site(packet, 'SourceTown', 'left')
        self.assertEqual(m.device_condition(site['device_entries'],20),'operating')
        with self.assertRaisesRegex(m.SourceError, 'state missing'):
            m.device_condition(site['device_entries'],21)

    def test_comparison_rejects_changed_fixed_condition_and_missing_variable(self):
        left = {'case_id':'a','map_hash':'x','turn_hash':'y','camera_hash':'z','ped_half':'destination'}
        right = dict(left,case_id='b',ped_half='opposite')
        m.audit_comparison(left,right,['map_hash','turn_hash','camera_hash'],'ped_half')
        with self.assertRaisesRegex(m.SourceError, 'fixed comparison changed'):
            m.audit_comparison(left,dict(right,map_hash='different'),['map_hash'],'ped_half')
        with self.assertRaisesRegex(m.SourceError, 'variable source'):
            m.audit_comparison(left,dict(right,ped_half=None),['map_hash'],'ped_half')


if __name__ == '__main__':
    unittest.main()
