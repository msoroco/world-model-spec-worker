import json
from pathlib import Path
import unittest
from xml.etree import ElementTree as ET

class OfficialDeviceConstruction(unittest.TestCase):
    def test_exact_device_identity_and_law_source(self):
        root=Path(__file__).resolve().parents[1]
        config=json.loads((root/'config.json').read_text())
        self.assertIn(config['case_suffix'],('exception_2_2','exception_3_2'))
        self.assertEqual(config['law_id'],'LVMC-11-52-130-A11')
        road=ET.fromstring((root/'road.xodr').read_text())
        destination=next(r for r in road.findall('road') if r.attrib['id']=='2')
        signals=destination.find('signals').findall('signal')
        self.assertEqual(len(signals),1)
        signal=signals[0]
        self.assertEqual((signal.attrib['id'],signal.attrib['country'],signal.attrib['type']),('620','US','206'))
        self.assertEqual((signal.attrib['s'],signal.attrib['t']),('1.0','-6.2'))
        self.assertFalse(config.get('physical_device_observed',False))

if __name__=='__main__':unittest.main()
