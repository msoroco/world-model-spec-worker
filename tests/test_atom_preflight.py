import unittest
from pathlib import Path

from worker_exchange.atom_preflight import check_required_atoms
from worker_exchange.package_compatibility import check_source_packets


RUNTIME = Path(__file__).resolve().parents[1] / 'runtime/main-pipeline-v1'


class WorkerAtomPreflightTests(unittest.TestCase):
    def test_real_supported_atom(self):
        self.assertTrue(check_required_atoms(RUNTIME, ['kin.position']))

    def test_derived_law_term_cannot_be_core_atom(self):
        with self.assertRaisesRegex(ValueError, 'Unknown Core required atom: drv.turning'):
            check_required_atoms(RUNTIME, ['drv.turning'])

    def test_conditional_atom_needs_packet(self):
        with self.assertRaisesRegex(ValueError, 'needs source packets: st.one_way_roadway'):
            check_required_atoms(RUNTIME, ['st.one_way_roadway'])

    def test_conditional_atom_with_packet(self):
        self.assertTrue(check_required_atoms(RUNTIME, ['st.one_way_roadway'], ['scenario_geometry']))

    def test_declared_packet_must_be_in_diagnostic_fixture(self):
        with self.assertRaisesRegex(ValueError, 'missing declared source packet'):
            check_source_packets({'source_packets':['scenario_geometry']}, {})
        check_source_packets({'source_packets':['scenario_geometry']}, {'scenario_geometry.json':'hash'})

    def test_unsupported_atom(self):
        with self.assertRaisesRegex(ValueError, 'lacks a supported adapter path: ru.trailer_or_combination'):
            check_required_atoms(RUNTIME, ['ru.trailer_or_combination'])

    def test_duplicate_atom(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            check_required_atoms(RUNTIME, ['kin.position', 'kin.position'])


if __name__ == '__main__':
    unittest.main()
