import hashlib
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
from opposing_turn_directed_runner import check_config, device_inventory


class FakeMap:
    def to_opendrive(self):
        return '<OpenDRIVE><road id="17"><signals><signal id="s1"/></signals></road></OpenDRIVE>'


class DirectedRunnerTest(unittest.TestCase):
    def test_both_exact_cases_and_verified_candidate(self):
        construction=json.loads((HERE/'construction-front_pass_no_device.json').read_text())
        config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
        for suffix in ('front_pass_device_alternate','rear_pass_device_alternate'):
            case=HERE.name+'__'+suffix
            config['selected_case_id']=case
            config['case']['case_id']=case
            self.assertEqual(len(check_config(config)),3)
        xml=FakeMap().to_opendrive()
        survey={'opendrive_sha256':hashlib.sha256(xml.encode()).hexdigest(),
                'source_kind':'operator_observed_native_device','road_id':17,
                'signal_id':'s1','instruction_text':'observed direction, pending legal review',
                'observation_reference':'native-device-observation-17',
                'observed_direction':'directs_alternate'}
        pair={'subject':{'approach_road_id':17},'opposing':{'approach_road_id':18}}
        self.assertEqual(device_inventory(FakeMap(),pair,survey)['governing_device'],'directs_alternate')
        with self.assertRaises(ValueError):device_inventory(FakeMap(),pair,survey|{'signal_id':'bad'})

    def test_uncontrolled_case_rejected(self):
        construction=json.loads((HERE/'construction-front_pass_no_device.json').read_text())
        config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
        with self.assertRaises(ValueError):check_config(config)
