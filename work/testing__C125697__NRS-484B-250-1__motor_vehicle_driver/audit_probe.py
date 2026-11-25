"""CPU proof of the independent delivery audit's source policy only."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_delivery_audit import staged
import delivery_audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    suffix = args.case.rsplit("__", 1)[-1]
    if suffix not in ("precedence", "advance"):
        raise ValueError("wrong exact audit case")
    args.output.mkdir(parents=True, exist_ok=False)
    attempt = args.output / "attempt"
    case = staged(attempt, suffix, 60 if suffix == "precedence" else 45)
    if args.negative:
        (attempt / "overview.mkv").write_bytes(b"tampered")
    proof = delivery_audit.audit_sources(attempt, case)
    if args.negative:
        raise ValueError("negative source alteration was accepted")
    print(json.dumps({"format": "worker-delivery-audit-cpu-policy-proof",
                      "case_id": case, "passed": True,
                      "physical_acceptance_claimed": False,
                      "source_sha256": proof["source_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
