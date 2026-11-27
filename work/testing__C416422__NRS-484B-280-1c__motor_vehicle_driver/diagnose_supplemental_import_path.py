"""Read-only, non-gate diagnosis of the supplemental assignment import lookup.

Run only with SCENARIO_PIPELINE_OUTPUT_ROOT set below .runtime-work/.
This does not change the frozen runtime, result statuses, or strict CLI result.
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))
from worker_exchange import portable, preparation
from worker_exchange.branch_coverage import assignment_path, assignments
from worker_exchange.common import read


def main():
    output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    scratch = (REPO / ".runtime-work").resolve()
    if output != scratch and scratch not in output.parents:
        raise ValueError("Output root must be under .runtime-work")
    batch = read(REPO / "batch.json")
    items = assignments(REPO, batch)
    ids = [aid for aid, item in items.items()
           if item.get("supplemental") and "__NRS-484B-280-1c__" in aid]
    if len(ids) != 4:
        raise ValueError("Expected four NRS-484B-280-1c supplemental bindings")
    findings = []
    original_read = portable.read
    for aid in ids:
        missing = REPO / "inputs" / aid / "assignment.json"
        actual = assignment_path(REPO, aid, items[aid])
        try:
            portable.validate_imports(REPO, aid)
        except FileNotFoundError as error:
            if Path(error.filename) != missing:
                raise
            direct = "missing supplemental input path"
        else:
            raise AssertionError("Unmodified import validator unexpectedly passed: " + aid)

        def corrected_read(path):
            return original_read(actual if Path(path) == missing else path)

        with patch.object(portable, "read", side_effect=corrected_read):
            portable.validate_imports(REPO, aid)
        findings.append({"assignment_id": aid,
                         "unmodified": direct,
                         "contract_path": str(actual.relative_to(REPO)),
                         "path_corrected_imports": "passed"})
    own = "testing__C416422__NRS-484B-280-1c__motor_vehicle_driver"
    missing = REPO / "inputs" / own / "assignment.json"
    actual = assignment_path(REPO, own, items[own])
    result_path = REPO / "work" / own / "result.json"
    original_preparation_read = preparation.read

    def scoped_read(path):
        value = original_preparation_read(path)
        if Path(path) == result_path:
            return dict(value, status="ready", reason=None)
        return value

    def scoped_portable_read(path):
        return original_read(actual if Path(path) == missing else path)

    with patch.object(preparation, "read", side_effect=scoped_read), patch.object(
        portable, "read", side_effect=scoped_portable_read
    ):
        preparation.check(REPO, complete=True, require_ready=True, assignment=own)
    print(json.dumps({"format": "worker-supplemental-import-path-diagnostic",
                      "is_strict_gate": False,
                      "virtual_ready_and_path_corrected_scoped_static_check": "passed",
                      "findings": findings}, indent=2))


if __name__ == "__main__":
    main()
