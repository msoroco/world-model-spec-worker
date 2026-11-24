"""Exercise the saved-only C230222 source finalizer on a CPU fixture."""

import json
import os
import shutil
import tempfile
from pathlib import Path

from saved_source_finalizer import ASSIGNMENT, SOURCES, finalize, sha


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIXTURE = REPO / ".runtime-work/c230222-runtime-frame-map-v1"


def reject(label, attempt, seal, contains):
    try:
        finalize(attempt, seal)
    except ValueError as error:
        if contains not in str(error):
            raise AssertionError(f"{label}: unexpected rejection: {error}") from error
        return {"mutation": label, "error": str(error)}
    raise AssertionError(f"{label}: invalid source accepted")


def main():
    scratch = REPO / ".runtime-work"
    assert scratch.is_dir() and FIXTURE.is_dir()
    assert Path(os.environ["TMPDIR"]).resolve().is_relative_to(scratch.resolve())
    seal = {"case_id": ASSIGNMENT + "__reference", "candidate_id": "primary",
            "native_exit_code": 0, "source_kind": "synthetic_native_sample",
            "source_sha256": {name: sha(FIXTURE / name) for name in SOURCES}}
    result = finalize(FIXTURE, seal)
    assert result["recorded_only"] and result["sample_count"] == 600
    assert result["driver_attention_to_operation"] is None and result["legal_verdict"] is None
    negatives = []
    with tempfile.TemporaryDirectory(prefix="c230222-saved-finalizer-", dir=scratch) as temp:
        temp = Path(temp)
        for name in SOURCES:
            target = temp / name
            if name == "native-ego-frames.jsonl":
                shutil.copyfile(FIXTURE / name, target)
            else:
                target.symlink_to(FIXTURE / name)
        with (temp / "native-ego-frames.jsonl").open("ab") as output:
            output.write(b"\n")
        negatives.append(reject("changed_native_trace", temp, seal,
                                "Sealed saved source differs: native-ego-frames.jsonl"))
        wrong_case = dict(seal, case_id=ASSIGNMENT + "__other")
        negatives.append(reject("wrong_exact_case", FIXTURE, wrong_case,
                                "Exact saved case identity required"))
        incomplete = dict(seal, source_sha256={name: value for name, value in
                                               seal["source_sha256"].items()
                                               if name != "driver_reference.mkv"})
        negatives.append(reject("missing_camera_seal", FIXTURE, incomplete,
                                "Complete sealed source inventory required"))
    print(json.dumps({"format": "c230222-saved-source-finalizer-cpu-proof-v1",
                      "passed": True, "source_fixture": "pinned FrameMap synthetic sample",
                      "source_fixture_path": str(FIXTURE.relative_to(REPO)),
                      "source_seal_sha256": __import__("hashlib").sha256(
                          json.dumps(seal, sort_keys=True).encode()).hexdigest(),
                      "finalized_result": result, "negative_rejections": negatives,
                      "original_native_observed": False,
                      "physical_or_legal_completion_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
