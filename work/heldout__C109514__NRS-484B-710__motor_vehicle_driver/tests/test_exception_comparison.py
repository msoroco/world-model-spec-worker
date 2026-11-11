import json
from pathlib import Path
import sys
import tempfile
import unittest


folder = Path(__file__).resolve().parents[1]
repo = folder.parents[1]
sys.path.insert(0, str(folder))
sys.path.insert(1, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
import exception_comparison_audit


class ExceptionComparisonTests(unittest.TestCase):
    def test_complete_conjunction_and_missing_packet_rejection(self):
        with tempfile.TemporaryDirectory(prefix='c109514-conjunction-',
                                          dir=repo / '.runtime-work') as temp:
            base = Path(temp)
            names = ('ordinary_police_at499', 'authorized_offduty_at499',
                     'unauthorized_onduty_at499', 'authorized_police_at499')
            roots = {}
            for name in names:
                roots[name] = base / name
                materialize(repo, folder / 'cases' / name / 'diagnostic-recipe.json', roots[name])
            self.assertEqual(exception_comparison_audit.audit_conjunction(roots)['case_count'], 4)
            (roots['authorized_offduty_at499'] / 'source_packets/authorization.json').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source'):
                exception_comparison_audit.audit_conjunction(roots)

    def test_fixed_originals_and_packet_rejection(self):
        with tempfile.TemporaryDirectory(prefix='c109514-exception-audit-',
                                          dir=repo / '.runtime-work') as temp:
            root = Path(temp)
            ordinary, authorized = root / 'ordinary', root / 'authorized'
            for suffix, path in (('ordinary_police_at499', ordinary),
                                 ('authorized_police_at499', authorized)):
                materialize(repo, folder / 'cases' / suffix / 'diagnostic-recipe.json', path)
            self.assertTrue(exception_comparison_audit.audit(ordinary, authorized)['passed'])
            packet = authorized / 'source_packets/official_business.json'
            packet.write_text(packet.read_text().replace('"asserted": true', '"asserted": false'))
            with self.assertRaisesRegex(ValueError, 'packet hash differs'):
                exception_comparison_audit.audit(ordinary, authorized)
            materialize_source = json.loads((folder / 'cases/authorized_police_at499/diagnostic.json').read_text())
            packet.write_text(materialize_source['files']['source_packets/official_business.json'])
            footprint = ordinary / 'participant_footprints.jsonl'
            footprint.write_text(footprint.read_text().replace('"ego_id":"ego"', '"ego_id":"other"', 1))
            with self.assertRaisesRegex(ValueError, 'changed fixed original'):
                exception_comparison_audit.audit(ordinary, authorized)


if __name__ == '__main__':
    unittest.main()
