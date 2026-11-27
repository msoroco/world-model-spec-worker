"""Test route source gate and measured passage, including failure controls."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from route_measure import load_review, measure

CASE='testing__C393410__LVMC-11-48-060__motor_vehicle_driver__through_no_enroute'


def packet(source_sha):
    return {'format':'worker-reviewed-truck-route-site','case_id':CASE,'diagnostic_fixture':True,
        'source_provenance':{'kind':'diagnostic_fixture','files':[{'path':'designation.txt','sha256':source_sha}]},
        'site':{'municipal_jurisdiction_reviewed':True,'chapter_scope_reviewed':True,
            'truck_routes':{'origin':{'road_id':10,'designation_source_sha256':source_sha},'destination':{'road_id':30,'designation_source_sha256':source_sha}},
            'intervening_street':{'road_id':20,'designation':'non_truck','designation_source_sha256':source_sha},
            'governing_controls_reviewed':True},
        'itinerary':{'route_use':'through','waypoints_xy_m':[[0,0],[10,0],[20,0]],
            'origin_on_truck_route':True,'entered_intervening_street':True,'destination_on_truck_route':True},
        'enroute_purpose':{'kind':'none','required_enroute_reviewed':False},'fps':20,
        'frames':[{'frame':100+i,'time_s':i*.05,'ego_actor_id':1,'position_xy_m':[i*10,0],
            'road_id':road_id,'street_designation':'truck_route' if road_id!=20 else 'non_truck',
            'activity_kind':None} for i,road_id in enumerate((10,20,30))]}


class RouteTests(unittest.TestCase):
    def test_through_route_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'designation.txt';source.write_text('reviewed source\n');digest=hashlib.sha256(source.read_bytes()).hexdigest()
            doc=root/'review.json';data=packet(digest);doc.write_text(json.dumps(data))
            self.assertEqual(load_review(doc,root,CASE,diagnostic=True)['case_id'],CASE)
            self.assertTrue(measure(doc)['destination_truck_route_observed'])
            data['frames'][-1]['road_id']=20;doc.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'incomplete'):measure(doc)
            data=packet(digest);data['enroute_purpose']={'kind':'pick_up','required_enroute_reviewed':True,
                'premises_source_sha256':digest,'activity_source_sha256':digest}
            doc.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'activity'):measure(doc)
            data=packet(digest);data['source_provenance']['files'][0]['sha256']='0'*64;doc.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'hash differs'):load_review(doc,root,CASE,diagnostic=True)


if __name__=='__main__':unittest.main()
