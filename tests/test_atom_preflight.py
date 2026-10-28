import unittest
from pathlib import Path

from worker_exchange.atom_preflight import check_required_atoms


RUNTIME = Path(__file__).resolve().parents[1] / 'runtime/main-pipeline-v1'


class WorkerAtomPreflightTests(unittest.TestCase):
    def test_real_supported_atom(self):
        self.assertTrue(check_required_atoms(RUNTIME, ['kin.position']))

    def test_derived_law_term_cannot_be_core_atom(self):
        with self.assertRaisesRegex(ValueError, 'Unknown Core required atom: drv.turning'):
            check_required_atoms(RUNTIME, ['drv.turning'])

    def test_real_but_unsupported_core_atom(self):
        with self.assertRaisesRegex(ValueError, 'lacks a supported adapter path: st.one_way_roadway'):
            check_required_atoms(RUNTIME, ['st.one_way_roadway'])

    def test_duplicate_atom(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            check_required_atoms(RUNTIME, ['kin.position', 'kin.position'])


if __name__ == '__main__':
    unittest.main()
