import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from geometry_statutory import CASES,check,open_drive
from statutory_context import inspect
from measure_statutory import measure

class StatutoryAlternativeProofs(unittest.TestCase):
    def test_authored_railroad_and_one_way_geometry(self):
        result=check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['case_results']['rail_reference']['sampled_relation'],'outside_100_ft')
        self.assertEqual(result['case_results']['rail_contrast']['sampled_relation'],'within_100_ft')
        self.assertTrue(result['case_results']['oneway_present']['one_way_proposed'])

    def test_source_context_positive_and_negative(self):
        frames=list(range(100,580))
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);context=root/'statutory_context.json';survey_path=root/'road_geometry.json';road=root/'road.xodr'
            for case,spec in CASES.items():
                one_way=spec['one_way'];rail=case.startswith('rail_')
                directions={'approach_forward':[1,0],
                    'approach_opposing':[1,0] if one_way else [-1,0],
                    'destination_forward':[1,0],
                    'destination_opposing':[1,0] if one_way else [-1,0]}
                survey={'native_map_sha256':'a'*64,'road_directions_native':directions,
                    'approach_boundary_x_m':spec['boundary_x_m']}
                survey_path.write_text(json.dumps(survey));road.write_text(open_drive(case))
                packet={'source_kind':'native_statutory_context_schema','case_suffix':case,
                    'zone_kind':spec['zone'],'one_way':one_way,'railroad_crossing':rail,
                    'railroad_crossing_object_id':'701' if rail else None,
                    'boundary_x_m':spec['boundary_x_m'],'native_map_sha256':'a'*64,
                    'original_frames':list(frames),'road_directions_native':directions,
                    'physical_observation_claimed':False,'legal_verdict':None}
                context.write_text(json.dumps(packet))
                with self.subTest(case=case):
                    result=inspect(context,case,frames,survey_path,road)
                    self.assertEqual(result['original_frames'],480)
                    packet['original_frames'].pop();context.write_text(json.dumps(packet))
                    with self.assertRaisesRegex(ValueError,'does not join'):
                        inspect(context,case,frames,survey_path,road)
            context.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                inspect(context,'rail_reference',frames,survey_path,road)

    def test_original_body_measurement_and_hash_negative(self):
        with tempfile.TemporaryDirectory() as temporary:
            source=Path(temporary)/'samples.jsonl'
            for case,spec in CASES.items():
                x=-75 if case=='rail_reference' else -45 if case=='rail_contrast' else -20
                rows=[{'native_frame':100+i,'video_frame':i,'time_s':.05*(i+1),
                    'body_xy_m':[[x-2.6,.65],[x-2.6,2.85],[x+2.6,2.85],[x+2.6,.65]],
                    'speed_m_s':5.0,'two_way_native_survey':not spec['one_way'],
                    'one_way_native_survey':spec['one_way']} for i in range(480)]
                source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
                digest=hashlib.sha256(source.read_bytes()).hexdigest()
                with self.subTest(case=case):
                    result=measure(rows,source,digest,spec['boundary_x_m'],spec['one_way'],spec['zone'])
                    self.assertEqual(result['sampled_relation'],
                        'outside_100_ft' if case=='rail_reference' else 'within_100_ft')
                    self.assertIsNone(result['legal_verdict'])
                    with self.assertRaisesRegex(ValueError,'hash'):
                        measure(rows,source,'0'*64,spec['boundary_x_m'],spec['one_way'],spec['zone'])

if __name__=='__main__':unittest.main()
