"""Fail-closed source and map binding checks for the marked-zone review."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('zone_source',ROOT/'zone_source.py')
zone_source=importlib.util.module_from_spec(spec);spec.loader.exec_module(zone_source)


class ZoneSourceTests(unittest.TestCase):
    def packet_zone(self):
        source=b'synthetic authority review fixture\n'
        packet={'format':'worker-zone-review-source-v1','reviewer':'CPU fixture',
                'review_method':'source/map join fixture','authority_citation':'fixture',
                'authority_source_sha256':hashlib.sha256(source).hexdigest(),
                'designation':'official_no_passing_zone','destination_kind':'other_left_turn',
                'subsections_3_and_4_reviewed':True,'road_id':1,'lane_id':-1,
                'zone_x_limits_m':[-10,10]}
        zone={'approach_road_id':1,'approach_lane_id':-1,'crossing_x_m':0,
              'sample_interval_max_m':5,'approach_marking_samples':[
                  {'requested_x_m':x,'mapped_x_m':x,'road_id':1,'lane_id':-1,'marking_type':'Solid'}
                  for x in (-5,-1)]}
        return packet,source,zone

    def test_reviewed_source_and_map_join(self):
        packet,source,zone=self.packet_zone()
        self.assertTrue(zone_source.validate(packet,source,zone)['zone_extent_verified'])

    def test_changed_source_and_unreviewed_exception_rejected(self):
        packet,source,zone=self.packet_zone()
        with self.assertRaisesRegex(ValueError,'source missing or changed'):
            zone_source.validate(packet,source+b'changed',zone)
        packet['subsections_3_and_4_reviewed']=False
        with self.assertRaisesRegex(ValueError,'exceptions'):
            zone_source.validate(packet,source,zone)

    def test_displaced_or_broken_striping_rejected(self):
        packet,source,zone=self.packet_zone()
        zone['approach_marking_samples'][1]['mapped_x_m']=3
        with self.assertRaisesRegex(ValueError,'outside reviewed zone'):
            zone_source.validate(packet,source,zone)
        zone['approach_marking_samples'][1]['mapped_x_m']=-1
        zone['approach_marking_samples'][1]['marking_type']='Broken'
        with self.assertRaisesRegex(ValueError,'lacks solid'):
            zone_source.validate(packet,source,zone)


if __name__=='__main__':unittest.main()
