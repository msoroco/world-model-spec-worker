"""Synthetic positive and damaged-source tests for independent comparison audit."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT") or not Path(
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve().is_relative_to(
            (REPO / ".runtime-work").resolve()):
    raise RuntimeError("Export runtime output root under .runtime-work")
sys.path.insert(0, str(ROOT))

from comparison_audit import audit
from prove_finalizer import build


def main():
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c135702-comparison-") as temp:
        folder = Path(temp)
        a, b = folder / "a", folder / "b"
        build(a, "a")
        build(b, "b")
        proof = audit(a, b, "synthetic_cpu")
        assert proof["passed"] and not proof["physical_causation_confirmed"]
        assert not proof["legal_verdict_claimed"]
        path = b / "native_samples.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            row["exceptions"]["traffic_conflict"] = True
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        try:
            audit(a, b, "synthetic_cpu")
        except ValueError as error:
            if "Comparison fixed source differs" not in str(error):
                raise
        else:
            raise AssertionError("Changed exception source passed comparison")
        print(json.dumps({"format": "c135702-comparison-cpu-proof-v1",
                          "case_ids": proof["case_ids"],
                          "fixed_conditions_checked": len(proof["fixed_conditions_checked"]),
                          "changed_exception_rejected": True,
                          "synthetic_only": True,
                          "legal_verdict_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
