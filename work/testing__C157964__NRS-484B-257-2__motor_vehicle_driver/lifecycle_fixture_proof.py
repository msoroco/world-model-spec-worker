"""Exercise capture closure, owner release, and saved-only replay on CPU sources."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASES = ("officer_controls_go", "officer_controls_hold", "officer_present_inactive")
SWEEP_CASES = tuple(f"c157964_sub2_judgment_{judgment}-{index:04d}"
                    for judgment in (3, 5) for index in range(3))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(suffix, output):
    if suffix not in CASES + SWEEP_CASES:
        raise ValueError("Unknown exact lifecycle case")
    from worker_exchange.runtime_cli import materialize
    from worker_exchange.fixture_recipe import materialize as materialize_fixture
    from worker_exchange.saved_processing import copy_sources, record_native_exit, acknowledge_owner_release
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import run as process_saved
    import shutil

    case_id = HERE.name + "__" + suffix
    manifest = HERE / "execution-manifest-draft.json"
    scratch = REPO / ".runtime-work/c157964-sub2/lifecycle" / (suffix + "-v2")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    fixture = scratch / "fixture"
    attempt = scratch / "attempt"
    derived = scratch / "derived"
    recipe = HERE / (suffix + "-fixture-recipe.json")
    materialize_fixture(REPO, recipe, fixture)
    materialize(manifest, case_id, attempt)
    copy_sources(fixture, attempt)
    (attempt / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "scope": "synthetic ownership lifecycle CPU fixture only"}) + "\n")
    seal = seal_capture(attempt, frames=3,
                        restoration={"restored": True, "fixture_only": True}, errors=[],
                        encoder_exit_codes={"diagnostic_encoder": 0})
    exited = record_native_exit(attempt)
    released = acknowledge_owner_release(attempt, attempt / "owner-release.json", True)
    saved = process_saved(manifest, case_id, attempt, derived,
                          REPO / "runtime/library",
                          REPO / ".runtime-work/c144550-decoder-current/.lake/build/bin/adapterCheck",
                          attempt / "owner-release.json")
    if saved.get("passed") is not True or saved.get("recorded_only") is not True:
        raise ValueError("Saved-only diagnostic replay did not pass")
    events = seal["events"] + [exited["event"], released["event"], "saved_processing_started"]
    expected = ["capture_finished", "encoders_closed", "restoration_verified",
                "native_exit", "owner_released", "saved_processing_started"]
    if events != expected:
        raise ValueError("Saved processing began before owner release")
    report = {"case_id": case_id, "events": events, "diagnostic_fixture": True,
              "physical_acceptance_claimed": False, "capture_seal_sha256": sha(attempt / "capture-seal.json"),
              "native_exit_sha256": sha(attempt / "native-exit.json"),
              "owner_release_sha256": sha(attempt / "owner-release.json"),
              "saved_processing": saved}
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": case_id, "events": events,
                      "saved_processing_passed": saved.get("passed")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    run(args.case, args.output)
