import importlib.util
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("c104538_electric_source_audit",ROOT/"audit-electric-source.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ElectricSourceAuditTest(unittest.TestCase):
    def test_current_selected_bicycle_cannot_claim_electric_class(self):
        proof=MODULE.audit()
        self.assertTrue(proof["passed"])
        self.assertFalse(proof["electric_bicycle_selected"])
        self.assertFalse(proof["electric_scooter_selected"])
        self.assertFalse(proof["electric_blueprint_inventory_checked_live"])
