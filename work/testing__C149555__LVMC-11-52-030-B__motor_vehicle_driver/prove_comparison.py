"""Exact-pair CPU source-isolation proof with synthetic test packets."""

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

from freight_contract import SourceError


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        "freight_comparison_tests", ROOT / "tests" / "test_saved_comparison.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if args.comparison not in module.comparison.PAIRS:
        raise ValueError("unknown exact freight comparison")
    left_variant, right_variant, _ = module.comparison.PAIRS[args.comparison]
    scratch = Path.cwd() / ".runtime-work" / "c149555-comparison-probes"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        base = Path(temporary)
        left_root, right_root = base / "left", base / "right"
        left = module.fixture(left_root, left_variant)
        right = module.fixture(right_root, right_variant)
        if args.negative:
            source = right_root / "overview.mkv"
            source.write_bytes(source.read_bytes() + b"tampered")
            try:
                module.comparison.audit_pair(left, right, args.comparison,
                                             attempt_roots=(left_root, right_root),
                                             media_probe=module.fake_probe)
            except SourceError as error:
                print("EXPECTED REJECTION: " + str(error))
                return 1
            raise AssertionError("tampered comparison media was accepted")
        receipt = module.comparison.audit_pair(left, right, args.comparison,
                                               attempt_roots=(left_root, right_root),
                                               media_probe=module.fake_probe)
        if not receipt["source_integrity"] or not receipt["physical_case_completion"]:
            raise AssertionError("comparison source isolation failed")
        print(json.dumps({"comparison_id": args.comparison,
                          "fixed_conditions_checked": receipt["fixed_conditions_checked"],
                          "deliberate_measurement": receipt["deliberate_measurement"],
                          "source_integrity": True, "synthetic_cpu_fixture": True,
                          "physical_acceptance_claimed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
