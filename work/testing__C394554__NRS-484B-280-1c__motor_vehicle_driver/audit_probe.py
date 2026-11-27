"""Exercise the independent transit auditor with CPU-only synthetic originals."""
import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    phase = args.case.rsplit("__", 1)[-1]
    if args.case != ROOT.name + "__" + phase or phase not in ("waiting_at_stop", "boarding_bus"):
        raise ValueError("wrong exact transit case")
    spec = importlib.util.spec_from_file_location("audit_fixture", ROOT / "tests/test_delivery_comparison_audit.py")
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    builder = fixture.AuditTests()
    builder.root = output
    attempt, processing, decode, case = builder.fixture(phase)
    if args.negative:
        with (attempt / "encounter-history.jsonl").open("a") as stream:
            stream.write("{}\n")
    value = fixture.delivery.audit(attempt, processing, decode, case,
                                   media_verify=lambda *a, **k: True)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
