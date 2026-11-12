"""CPU test for the original receipt schema; no original capture is asserted."""
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from camera_lifecycle_audit import CAMERAS, check_release
from original_postprocess_handoff import EVENTS, bind_processing, verify_closure
import original_postprocess_handoff as handoff_module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def reject(name, action, rejected):
    try:
        action()
    except ValueError:
        rejected.append(name)
    else:
        raise AssertionError("Owner handoff mutation accepted: " + name)


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = manifest["cases"][0]
    case, construction_sha256 = entry["case_id"], entry["construction_sha256"]
    runtime_work = ROOT / ".runtime-work"
    runtime_work.mkdir(exist_ok=True)
    rejected = []
    with tempfile.TemporaryDirectory(prefix="c110454-owner-schema-", dir=runtime_work) as temp:
        attempt = Path(temp) / "attempt"
        attempt.mkdir()
        shutil.copy2(HERE / entry["construction"], attempt / "construction.json")
        (attempt / "runner.py").write_text("# CPU schema mock; no CARLA execution\n")
        write(attempt / "config.json", {"case_id": case, "candidate_id": "primary"})
        write(attempt / "candidate-selection.json", {"candidate_id": "primary"})
        write(attempt / "acquisition-provenance.json",
              {"provenance_kind": "native", "diagnostic_fixture": False,
               "cpu_fixture_mock": True})
        (attempt / "capture").mkdir()
        for name in ("native_samples.jsonl", "trace.jsonl", "video_frames.jsonl",
                     "capture/evidence.jsonl"):
            (attempt / name).write_text('{"cpu_fixture_mock":true}\n')
        for camera in CAMERAS:
            (attempt / (camera + ".mkv")).write_text("CPU mock camera: " + camera)
        source_names = ["construction.json", "runner.py", "config.json",
                        "candidate-selection.json",
                        "acquisition-provenance.json", "native_samples.jsonl",
                        "trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
                        *(name + ".mkv" for name in CAMERAS)]
        sources = {name: sha(attempt / name) for name in source_names}
        revision = {"construction_sha256": construction_sha256,
                    "runner_sha256": sha(attempt / "runner.py")}
        seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
                "diagnostic_fixture": False, "frames": 480, "events": EVENTS[:3],
                "native_revision": revision, "sources": sources,
                "cpu_fixture_mock": True}
        write(attempt / "capture-seal.json", seal)
        exited = {"event": "native_exit", "native_process_exit_code": 0,
                  "capture_command_failed": False,
                  "capture_seal_sha256": sha(attempt / "capture-seal.json"),
                  "native_revision": revision, "cpu_fixture_mock": True}
        write(attempt / "native-exit.json", exited)
        owner = {"event": "owner_released", "operator_attested": True,
                 "no_resource_operation_performed": True,
                 "native_construction_sha256": construction_sha256,
                 "native_exit_sha256": sha(attempt / "native-exit.json"),
                 "cpu_fixture_mock": True}
        owner_path = attempt / "owner-release.json"
        write(owner_path, owner)
        closure = verify_closure(attempt, owner_path, case, "primary", construction_sha256)
        processed = {"format": "worker-saved-processing", "case_id": case,
                     "candidate_id": "primary", "passed": True, "recorded_only": True,
                     "originals_preserved": True,
                     "events": ["saved_processing_started", "selected_analysis_executed",
                                "originals_verified"],
                     "native_revision": {"construction_sha256": construction_sha256},
                     "original_source_hashes": sources, "cpu_fixture_mock": True}
        processing_path = Path(temp) / "processing.json"
        write(processing_path, processed)
        handoff = bind_processing(attempt, owner_path, processing_path, case,
                                  "primary", construction_sha256)
        cameras = {name: {"sha256": sources[name + ".mkv"]} for name in CAMERAS}
        check_release(seal, exited, owner, processed, handoff, case, "primary",
                      closure["capture_seal_sha256"], closure["native_exit_sha256"],
                      closure["owner_release_sha256"], sha(processing_path), cameras)
        output = Path(temp) / "saved"
        version = output / "v0001"
        called = []
        def fake_process(command, **_kwargs):
            called.append(command)
            version.mkdir(parents=True)
            write(version / "processing.json", processed)
            return SimpleNamespace(returncode=0,
                                   stdout=json.dumps({"version": str(version)}), stderr="")
        args = SimpleNamespace(manifest=HERE / "execution-manifest.json", case=case,
                               attempt=attempt, output=output, library="unused-cpu-library",
                               validator="unused-cpu-validator", owner_release_receipt=owner_path)
        with mock.patch.object(handoff_module.subprocess, "run", side_effect=fake_process):
            wrapped = handoff_module.run(args)
        if (not called or "--owner-release-receipt" not in called[0] or
                json.loads((version / "owner-handoff.json").read_text())["owner_release_sha256"] != sha(owner_path) or
                wrapped["recording_accepted"] is not False):
            raise AssertionError("Original postprocessing wrapper lost source-bound release")
        camera_path = attempt / "overview.mkv"
        original_camera = camera_path.read_text()
        camera_path.write_text("changed mock camera")
        reject("changed_sealed_source", lambda: verify_closure(
            attempt, owner_path, case, "primary", construction_sha256), rejected)
        camera_path.write_text(original_camera)
        reject("wrong_construction", lambda: verify_closure(
            attempt, owner_path, case, "primary", "0" * 64), rejected)
        reject("wrong_native_exit", lambda: check_release(
            seal, {**exited, "native_process_exit_code": 1}, owner, processed, handoff,
            case, "primary", closure["capture_seal_sha256"],
            closure["native_exit_sha256"], closure["owner_release_sha256"],
            sha(processing_path), cameras), rejected)
        reject("wrong_owner_event", lambda: check_release(
            seal, exited, {**owner, "event": "owner_release"}, processed, handoff,
            case, "primary", closure["capture_seal_sha256"],
            closure["native_exit_sha256"], closure["owner_release_sha256"],
            sha(processing_path), cameras), rejected)
        reject("stale_owner_hash", lambda: check_release(
            seal, exited, owner, processed, {**handoff, "owner_release_sha256": "0" * 64},
            case, "primary", closure["capture_seal_sha256"],
            closure["native_exit_sha256"], closure["owner_release_sha256"],
            sha(processing_path), cameras), rejected)
        reject("stale_processing_hash", lambda: check_release(
            seal, exited, owner, processed, handoff, case, "primary",
            closure["capture_seal_sha256"], closure["native_exit_sha256"],
            closure["owner_release_sha256"], "0" * 64, cameras), rejected)
        reject("early_saved_processing", lambda: check_release(
            seal, exited, owner, {**processed, "events": ["analysis_started"]},
            handoff, case, "primary", closure["capture_seal_sha256"],
            closure["native_exit_sha256"], closure["owner_release_sha256"],
            sha(processing_path), cameras), rejected)
        reject("changed_camera", lambda: check_release(
            seal, exited, owner, processed, handoff, case, "primary",
            closure["capture_seal_sha256"], closure["native_exit_sha256"],
            closure["owner_release_sha256"], sha(processing_path),
            {**cameras, "overview": {"sha256": "0" * 64}}), rejected)
        wrong = copy.deepcopy(processed)
        wrong["original_source_hashes"]["overview.mkv"] = "0" * 64
        write(processing_path, wrong)
        reject("saved_source_changed", lambda: bind_processing(
            attempt, owner_path, processing_path, case, "primary",
            construction_sha256), rejected)
    proof = {"format": "c110454-original-owner-handoff-cpu-proof-v1",
             "manifest_sha256": sha(HERE / "execution-manifest.json"),
             "case_id": case, "pinned_runtime_receipt_schema_tested": True,
             "postprocessing_wrapper_command_tested": True,
             "auditor_sha256": sha(HERE / "camera_lifecycle_audit.py"),
             "handoff_wrapper_sha256": sha(HERE / "original_postprocess_handoff.py"),
             "pinned_saved_processing_sha256": sha(ROOT / "runtime/pipeline/scenario_pipeline/worker_exchange/saved_processing.py"),
             "rejected_mutations": rejected, "cpu_fixture_mock": True,
             "original_native_capture_or_owner_release_claimed": False,
             "recordings_accepted": 0}
    path = HERE / "update031-original-owner-handoff-proof.json"
    write(path, proof)
    print(json.dumps({"rejected_mutations": rejected,
                      "original_native_capture_or_owner_release_claimed": False,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
