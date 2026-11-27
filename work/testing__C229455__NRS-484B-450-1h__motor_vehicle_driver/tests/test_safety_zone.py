from __future__ import annotations
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from safety_zone import CASES, THIRTY_FT_M, between_zone_curb, construct, measure_original, signed_end_station, validate_scene
from site_review import reviewed_site


def scene(case):
    zone = [0, 0, 20, 2]
    body = [9, 3, 11, 4.5]
    if case.placement == 'outside':
        body = [9, 5.5, 11, 7]
    elif case.placement == 'end_band':
        x = -case.offset_m if case.end == 'west' else 20 + case.offset_m
        body = [x - 1, 3, x + 1, 4.5]
    center = [(body[0]+body[2])/2, (body[1]+body[3])/2]
    item = {'cell_id':'C229455','actor':'motor_vehicle_driver','driver_present':True,
      'motor_vehicle':True,'highway_public_access':True,
      'safety_zone_designated_pedestrian_exclusive':True,
      'safety_zone_set_apart_visible':True,'safety_zone_marking_or_sign_source_sha256':'fixture',
      'placement':case.placement,'end':case.end,'activity':case.activity,
      'exception':case.exception,'zone_rect_m':zone,'target_body_rect_m':body,
      'adjacent_curb_y_m':5,'west_end_curb_point_m':[0,5],
      'east_end_curb_point_m':[20,5],'vehicle_target_xy':center,
      'vehicle_start_xy':[center[0]-12,center[1]],'traffic_start_xy':[-20, -2],
      'traffic_target_xy':[35,-2],
      'vehicle_route_xy':[[center[0]-12,center[1]],center],
      'traffic_route_xy':[[-20,-2],[35,-2]],'conflicting_traffic_id':'fixture-traffic',
      'authority_record_id':'fixture-authority'}
    for name in ('map','highway','zone','curb','designation','vehicle','driver','route',
                 'traffic','activity','exception'):
        item[name+'_source_sha256']='fixture-'+name
    return item

class Adapter:
    def __init__(self): self.calls=[]
    def place_zone(self,*a): self.calls.append(('zone',*a))
    def spawn_motor_vehicle(self,p): self.calls.append(('ego',p));return 'ego'
    def spawn_traffic(self,p): self.calls.append(('traffic',p));return 'traffic'
    def set_halt_route(self,*a): self.calls.append(('halt',*a))
    def set_traffic_route(self,*a): self.calls.append(('traffic_route',*a))
    def set_exception_context(self,*a): self.calls.append(('exception',*a))
    def destroy(self,*a): self.calls.append(('destroy',*a))

class SafetyZoneTests(unittest.TestCase):
    def test_statutory_distance_and_both_ends(self):
        self.assertAlmostEqual(THIRTY_FT_M,9.144)
        west=next(c for c in CASES if c.case_id=='west_end_below_30ft')
        east=next(c for c in CASES if c.case_id=='east_end_below_30ft')
        for case in (west,east):
            s=scene(case);validate_scene(s,case)
            self.assertAlmostEqual(signed_end_station(s['vehicle_target_xy'],s['west_end_curb_point_m'],s['east_end_curb_point_m'],case.end),case.offset_m)
    def test_all_case_geometry_and_calls(self):
        for case in CASES:
            s=scene(case);adapter=Adapter();construct(adapter,s,case)
            self.assertEqual([x[0] for x in adapter.calls],['zone','ego','traffic','halt','traffic_route','exception'])
            self.assertEqual(between_zone_curb(s['target_body_rect_m'],s['zone_rect_m'],s['adjacent_curb_y_m']),case.placement=='between')
    def test_false_designation_rejected(self):
        case=CASES[0];s=scene(case);s['safety_zone_designated_pedestrian_exclusive']=False
        with self.assertRaisesRegex(ValueError,'designation'):
            validate_scene(s,case)
    def test_wrong_end_station_rejected(self):
        case=next(c for c in CASES if c.case_id=='west_end_at_30ft');s=scene(case)
        s['target_body_rect_m'][0]+=0.2
        with self.assertRaisesRegex(ValueError,'station'):
            validate_scene(s,case)
    def test_source_packet_missing_rejected(self):
        with self.assertRaisesRegex(ValueError,'reviewed original site packet missing'):
            reviewed_site(ROOT/'does-not-exist.json', ROOT.name+'__between_park')
