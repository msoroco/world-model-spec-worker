import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from opposing_turn_device_source import verify_device_candidate


XML='<OpenDRIVE><road id="17"><signals><signal id="s1"/></signals></road></OpenDRIVE>'
BASE={'opendrive_sha256':hashlib.sha256(XML.encode()).hexdigest(),
      'source_kind':'operator_observed_native_device','road_id':17,'signal_id':'s1',
      'instruction_text':'operator transcription pending independent applicability review',
      'observation_reference':'native-device-observation-17',
      'observed_direction':'directs_alternate'}


class DeviceSourceTest(unittest.TestCase):
    def test_exact_map_signal_is_candidate_only(self):
        result=verify_device_candidate(XML,{17,18},BASE)
        self.assertEqual(result['governing_device'],'directs_alternate')
        self.assertEqual(result['legal_device_applicability'],'unreviewed')

    def test_stale_or_unrelated_source_rejected(self):
        for change in ({'opendrive_sha256':'0'*64},{'signal_id':'missing'},
                       {'road_id':19},{'observation_reference':''},
                       {'observed_direction':'unresolved'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                verify_device_candidate(XML,{17,18},BASE|change)
