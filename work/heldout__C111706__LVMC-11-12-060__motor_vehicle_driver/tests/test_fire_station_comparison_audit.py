import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fire_station_comparison_audit import COMPARISONS, CAMERAS, FIXED, audit


def materialize(branch,output):
    folder=ROOT if branch=='front_entrance_turn' else ROOT/'cases'/branch
    diagnostic=folder/('diagnostic-front_entrance_turn.json' if folder==ROOT else 'diagnostic.json')
    config=folder/'config.json'
    data=json.loads(diagnostic.read_text())
    output.mkdir()
    for name in ('subject_original.jsonl',*FIXED):
        (output/name).write_text(data['files'][name])
    (output/'config.json').write_bytes(config.read_bytes())
    for name in CAMERAS:
        (output/name).write_bytes(b'synthetic camera source placeholder')


class ComparisonTests(unittest.TestCase):
    def test_three_source_contrasts_and_fixed_source_negative(self):
        for comparison,(left,right) in COMPARISONS.items():
            with self.subTest(comparison=comparison),tempfile.TemporaryDirectory() as temp:
                a,b=Path(temp)/'left',Path(temp)/'right'
                materialize(left,a);materialize(right,b)
                result=audit(a,b,comparison)
                self.assertEqual(result['comparison_id'],comparison)
                self.assertEqual(result['station_identity'],'unreviewed')
                self.assertFalse(result['physical_acceptance_claimed'])
                source=b/'other_original.jsonl'
                source.write_text(source.read_text().replace('12.0','13.0',1))
                with self.assertRaisesRegex(ValueError,'fixed original source'):
                    audit(a,b,comparison)

    def test_missing_named_camera_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            a,b=Path(temp)/'left',Path(temp)/'right'
            materialize('front_entrance_turn',a)
            materialize('remote_reference',b)
            (b/'overview.mkv').unlink()
            with self.assertRaisesRegex(ValueError,'named station source camera'):
                audit(a,b,'entrance_vs_remote')


if __name__=='__main__':unittest.main()
