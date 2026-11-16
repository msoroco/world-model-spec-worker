"""CPU construction/readback probes for all planned exception road variants."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from exception_road import construct, readback

class ExceptionRoadProof(unittest.TestCase):
    def test_every_exception_geometry(self):
        matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
        reviewed=[]
        for case in matrix['cases']:
            xml=construct(case)
            observed=readback(xml)
            self.assertEqual(observed['sign_readback']['displayed_classes'],
                             case['sign_classes'])
            self.assertEqual(observed['mailbox_readback']['present'],
                             case['mailbox_requested'])
            self.assertEqual(observed['red_curb']['paint_color'],'red')
            reviewed.append(case['case_id'])
        self.assertEqual(len(reviewed),28)

    def test_absent_and_corrupt_features_reject(self):
        matrix=json.loads((ROOT/'exception-case-matrix.json').read_text())
        signed=next(c for c in matrix['cases'] if c['sign_classes'])
        xml=construct(signed)
        with self.assertRaisesRegex(ValueError,'Sign geometry'):
            readback(xml.replace('t="-7.5"','t="-9.5"'))
        with self.assertRaisesRegex(ValueError,'red paint'):
            readback(xml.replace('color="red"','color="white"'))
        mailbox=next(c for c in matrix['cases'] if c['mailbox_requested'])
        with self.assertRaisesRegex(ValueError,'Mail-drop geometry'):
            readback(construct(mailbox).replace('t="-7.4"','t="-9.4"'))

if __name__=='__main__':unittest.main()
