"""Read-only Native source preflight for selected lane-change delivery.

This checks source closure and measured physical evidence. It does not review
camera pixels for legal sufficiency or assert physical/legal acceptance.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source_path(attempt, name):
    rel = PurePosixPath(str(name))
    if rel.is_absolute() or not rel.parts or any(part in ("..", ".") for part in rel.parts):
        raise ValueError("Unsafe sealed source path")
    path = attempt.joinpath(*rel.parts)
    if path.is_symlink() or not path.is_file() or attempt not in path.resolve().parents:
        raise ValueError("Missing contained sealed source: " + str(name))
    return path


def selected_measurements(attempt, entry, case_id, sealed_sources, expected_frames=900):
    """Load the exact analyzer shipped in this sealed construction."""
    analyzer_name = entry["measurement_procedure"]["entrypoint"]
    analyzer = source_path(attempt, analyzer_name)
    if analyzer_name not in sealed_sources:
        raise ValueError("Selected analyzer is not sealed original implementation")
    selected_construction = read(attempt / "construction.json")
    embedded = [file["content"] for file in selected_construction["files"] if file["path"] == analyzer_name]
    if len(embedded) != 1 or hashlib.sha256(embedded[0].encode()).hexdigest() != sha(analyzer):
        raise ValueError("Selected analyzer differs from sealed construction")
    module_spec = importlib.util.spec_from_file_location("sealed_c144550_measurements", analyzer)
    if module_spec is None or module_spec.loader is None:
        raise ValueError("Selected analyzer cannot be loaded")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.measure_exact_case(attempt, case_id, expected_frames)


def audit(attempt, case_id, owner_receipt):
    attempt = Path(attempt).resolve()
    owner_receipt = Path(owner_receipt).resolve()
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    entry = next((item for item in manifest["cases"] if item["case_id"] == case_id), None)
    if entry is None:
        raise ValueError("Unknown selected lane-change case")
    provenance = read(attempt / "acquisition-provenance.json")
    if provenance != {"provenance_kind": "native", "diagnostic_fixture": False}:
        raise ValueError("Native non-diagnostic provenance required")
    seal_path = attempt / "capture-seal.json"
    if not seal_path.is_file():
        raise ValueError("Native capture seal required")
    seal = read(seal_path)
    if (seal.get("format") != "worker-sealed-capture" or seal.get("provenance_kind") != "native"
            or seal.get("diagnostic_fixture") is not False or seal.get("frames") != 900
            or seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"]
            or seal.get("source_digest") != digest(seal.get("sources", {}))):
        raise ValueError("Native capture seal or duration differs")
    sources = seal.get("sources", {})
    required = {"construction.json", "runner.py", "config.json", "lane_context.json",
                "lane_history.jsonl", "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl"}
    required.update(name + ".mkv" for name in CAMERAS)
    if not required <= set(sources):
        raise ValueError("Native capture seal omits required original source")
    for name, checksum in sources.items():
        if sha(source_path(attempt, name)) != checksum:
            raise ValueError("Sealed original changed: " + name)
    selection_path = attempt / "candidate-selection.json"
    selection = read(selection_path) if selection_path.is_file() else {"candidate_id": "primary"}
    candidate_id = selection.get("candidate_id")
    selected = entry if candidate_id == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == candidate_id), None)
    if selected is None:
        raise ValueError("Unknown selected fallback")
    if candidate_id != "primary" and not selection_path.is_file():
        raise ValueError("Fallback needs exact candidate selection")
    if selection_path.is_file() and (selection.get("case_id") != case_id
            or selection.get("construction_sha256") != selected["construction_sha256"]
            or selection.get("manifest_sha256") != sha(manifest_path)):
        raise ValueError("Native candidate selection differs from exact manifest")
    if sha(HERE / selected["construction"]) != selected["construction_sha256"]:
        raise ValueError("Selected construction source changed")
    if sha(attempt / "construction.json") != selected["construction_sha256"]:
        raise ValueError("Native construction differs from selected case")
    revision = {"construction_sha256": sha(attempt / "construction.json"),
                "runner_sha256": sha(attempt / "runner.py")}
    if seal.get("native_revision") != revision:
        raise ValueError("Native capture revision differs")
    exit_path = attempt / "native-exit.json"
    exit_record = read(exit_path)
    if (exit_record.get("event") != "native_exit" or exit_record.get("capture_seal_sha256") != sha(seal_path)
            or exit_record.get("native_revision") != revision):
        raise ValueError("Native exit does not bind sealed capture")
    owner = read(owner_receipt)
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True
            or owner.get("native_construction_sha256") != revision["construction_sha256"]
            or owner.get("native_exit_sha256") != sha(exit_path)
            or owner.get("no_resource_operation_performed") is not True):
        raise ValueError("Owner release does not bind Native exit")
    config = read(attempt / "config.json")
    if (config.get("selected_case_id") != case_id or config.get("law_id") != "NRS-484B-223-1b"
            or config.get("cell_id") != "C144550" or config.get("rate_hz") * config.get("duration_s") != 900):
        raise ValueError("Native exact configuration differs")
    measurements = selected_measurements(attempt, entry, case_id, sources)
    if not measurements["observed_signal_pattern_matches_plan"]:
        raise ValueError("Native signal pattern differs from selected construction")
    mapping = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines() if line.strip()]
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines() if line.strip()]
    capture = [json.loads(line) for line in (attempt / "capture/evidence.jsonl").read_text().splitlines() if line.strip()]
    if len(mapping) != len(trace) or len(capture) != 900:
        raise ValueError("Native original frame count differs")
    for index, (frame, motion, observation) in enumerate(zip(mapping, trace, capture)):
        native, time_s = frame.get("carla_frame"), frame.get("time_s")
        if (frame.get("video_frame") != index or native != motion.get("frame")
                or native != observation.get("original_frame") or not isinstance(time_s, (int, float))
                or not math.isfinite(time_s) or abs(time_s - motion.get("time_s", float("inf"))) > .001
                or abs(time_s - observation.get("recording_time_s", float("inf"))) > .001):
            raise ValueError("Native original frame/time join differs")
        people = observation.get("original_observations", {}).get("participants")
        if not isinstance(people, list) or len(people) < 2:
            raise ValueError("Native participant inventory incomplete")
        ids = [person.get("actor_id") for person in people if isinstance(person, dict)]
        if len(ids) != len(people) or len(set(ids)) != len(ids) or observation.get("actor_id") not in ids:
            raise ValueError("Native participant identities differ")
        if any(not isinstance(person.get("body_vertices_m"), list) or len(person["body_vertices_m"]) < 8
               for person in people):
            raise ValueError("Native participant bodies missing")
    cameras = {item["name"]: item for item in config.get("cameras", [])}
    if set(cameras) != set(CAMERAS):
        raise ValueError("Four Native cameras required")
    decodes = {}
    for name in CAMERAS:
        path = attempt / (name + ".mkv")
        probe = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(path)],
                               capture_output=True, text=True, check=True)
        streams = json.loads(probe.stdout).get("streams", [])
        if (len(streams) != 1 or (streams[0].get("width"), streams[0].get("height"))
                != (cameras[name]["width"], cameras[name]["height"])
                or int(streams[0].get("nb_read_frames", -1)) != 900):
            raise ValueError("Native camera frame count or dimensions differ: " + name)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
                                  "-f", "framemd5", "-"], capture_output=True, check=True)
        lines = [line for line in decoded.stdout.splitlines() if line and not line.startswith(b"#")]
        if len(lines) != 900:
            raise ValueError("Native full camera decode differs: " + name)
        decodes[name] = {"source_sha256": sha(path),
                         "decoded_frames_sha256": hashlib.sha256(b"\n".join(lines)).hexdigest()}
    return {"format": "worker-lane-change-native-source-preflight", "case_id": case_id,
            "candidate_id": candidate_id, "capture_seal_sha256": sha(seal_path),
            "owner_release_sha256": sha(owner_receipt), "original_measurement_hashes": measurements["sources"],
            "camera_decodes": decodes, "native_source_preflight_passed": True,
            "actual_pixels_reviewed": False, "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--owner-receipt", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.owner_receipt), sort_keys=True))
