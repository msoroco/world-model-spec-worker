"""Fake operator verifies original source joins and actor construction calls."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from native_capture import capture
from width_measurement import ASSIGNMENT
from test_alley_width_construction import site

SOURCE={"path":"reviewed/native-row.json","sha256":"b"*64}
PNG=b"\x89PNG\r\n\x1a\n"+b"source-shaped diagnostic"


class Operator:
    direction=1
    native_attested=False
    def __init__(self, case_id, missing=None):
        self.case_id=case_id;self.missing=missing;self.count=0;self.started=False;self.cleaned=False
    def get_map_packet(self, case_id):
        value=site();value.update(case_id=case_id,source_kind="original_native_geometry",
            public_highway_status=True,map_sha256=hashlib.sha256(b"<OpenDRIVE/>").hexdigest(),
            ego_blueprint_source="reviewed:ego-blueprint",ego_dimensions_source="reviewed:ego-dimensions",
            ego_vehicle_id="ego-1")
        value['cross_sections'].append({"station_m":51,"left_xy_m":[51,0],
                                        "right_xy_m":[51,5]})
        for key in ("public_highway_source","city_block_source","rear_access_source",
                    "abutting_property_source","through_connection_source","jurisdiction_source",
                    "ordinance_source","survey_source"):
            value[key]=SOURCE
        for section in value['cross_sections']:
            section['source']=SOURCE
        return value
    def get_opendrive_bytes(self):return b"<OpenDRIVE/>"
    def start(self,plan):self.started=True;self.plan=plan
    def read_actor_inventory(self):return {"ego_vehicle_id":"ego-1","ego_actual_blueprint":"vehicle.mock",
        "ego_actual_dimensions_m":{"length":4.5,"width":1.8},
        "other_vehicle_id":"other-1","other_actual_blueprint":"vehicle.other",
        "other_actual_dimensions_m":{"length":4.2,"width":1.8}}
    def tick(self):
        row={"frame":self.count,"time_s":self.count*0.05};self.count+=1;return row
    def read_width_history(self,frame):
        row={"frame":frame,"time_s":frame*0.05,"source":SOURCE,"ego_vehicle_id":"ego-1",
             "phase":"parked_hold" if 100 <= frame < 700 else "approach",
             "ego_body_polygon_m":[[49,0],[51,0],[51,1.8],[49,1.8]],
             "other_body_polygons_m":[],"other_vehicle_id":"other-1"}
        if self.missing=='source' and frame==150:row.pop('source')
        return row
    def read_cameras(self,frame):
        return {view:{"frame":frame,"time_s":frame*0.05,"png":PNG} for view in
                ("overview","approach","reference_corner","driver_reference")}
    def brake(self):pass
    def cleanup(self):self.cleaned=True


class CaptureTests(unittest.TestCase):
    def test_full_capture_joins_and_cleans(self):
        root=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=root) as td:
            actor=Operator(ASSIGNMENT+'__width_9_9ft')
            result=capture(actor,actor.case_id,Path(td)/'attempt')
            self.assertEqual(result['frame_count'],900)
            self.assertTrue(actor.started and actor.cleaned)
            self.assertTrue((Path(td)/'attempt'/'inventory.json').exists())
    def test_missing_original_source_rejected_and_cleans(self):
        root=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=root) as td:
            actor=Operator(ASSIGNMENT+'__width_9_9ft',missing='source')
            with self.assertRaisesRegex(ValueError,'source/frame'):
                capture(actor,actor.case_id,Path(td)/'attempt')
            self.assertTrue(actor.cleaned)
            self.assertFalse((Path(td)/'attempt').exists())


if __name__=='__main__':unittest.main()
