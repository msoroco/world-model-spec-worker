"""CPU protocol proof for exact freight delivery acceptance.

This uses a synthetic source fixture and mocks the unavailable physical and
pixel outcomes. It proves binding and rejection logic, not physical success.
"""

import argparse
import importlib.util
import sys
import unittest
from pathlib import Path

from freight_contract import SourceError


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
VARIANTS = {
    "freight_loading", "freight_unloading", "no_freight_activity",
    "noncommercial_loading", "outside_posted_time", "outside_yellow_zone",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.case not in {ASSIGNMENT + "__" + variant for variant in VARIANTS}:
        raise ValueError("unknown exact freight case")
    spec = importlib.util.spec_from_file_location(
        "freight_delivery_tests", ROOT / "tests" / "test_delivery_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DeliveryAuditTests.case_id = args.case
    if args.negative:
        test = module.DeliveryAuditTests("test_complete_saved_binding")
        test.setUp()
        try:
            (test.attempt / "raw.jsonl").write_text("changed\n", encoding="utf-8")
            try:
                test.run_audit()
            except SourceError as error:
                print("EXPECTED REJECTION: " + str(error))
                return 1
            raise AssertionError("stale original source was accepted")
        finally:
            test.doCleanups()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(module.DeliveryAuditTests)
    result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
    print("CPU protocol fixture only; original Native recording remains unreviewed")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
