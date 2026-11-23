"""Exercise saved C153046 schema against the pinned runtime with a CPU fixture."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
ASSIGNMENT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ASSIGNMENT))

from scenario_pipeline.worker_exchange.native_output import validate_result
from scenario_pipeline.batch_pipeline.validation import recording_evidence
from saved_measurement import finalize_attempt
from tests.test_saved_finalizer import attempt


def main():
    private = ROOT / ".runtime-work" / "c153046-saved-finalizer"
    private.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=private) as directory:
        root = Path(directory)
        case_id = attempt(root)
        report = finalize_attempt(root, root / "analysis-report.json")
        result = validate_result(json.loads((root / "result.json").read_text()))
        recording_evidence(result, result["recording_description"],
                           lambda reference: root / reference)
        if report["case_id"] != case_id or result["setup_confirmed"]:
            raise ValueError("diagnostic finalizer claimed physical setup")
    print("pinned native result and recording evidence schemas passed for CPU fixture", case_id)


if __name__ == "__main__":
    main()
