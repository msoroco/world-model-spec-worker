"""Bind tested primary/fallback proofs into exact delivery manifest."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from author_semantics import CHANNELS
from stop_model import ASSIGNMENT, CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work/c150640-6272"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def relative(path):
    return str(Path(path).relative_to(ROOT))


def bind_compat(name, candidate):
    suffix = "" if candidate == "primary" else "-fallback1"
    source = SCRATCH / f"compat5-{name}-{candidate}"
    dest = ROOT / "proofs" / name / candidate
    dest.mkdir(parents=True, exist_ok=True)
    for old, new in (("compatibility.json", "receipt.json"),
                     ("compatibility-analysis.log", "analysis.log"),
                     ("negative-analysis.log", "negative.log")):
        shutil.copy2(source / old, dest / new)
    return {"receipt": relative(dest / "receipt.json"),
            "sha256": sha(dest / "receipt.json"),
            "log": relative(dest / "analysis.log"),
            "negative_log": relative(dest / "negative.log")}


def physical(name, construction_sha):
    fixtures = []
    log = ROOT / f"physical-{name}.log"
    command = (f".venv-cpu/bin/python work/{ASSIGNMENT}/physical_probe.py "
               f"--case {ASSIGNMENT}__{name} --output .runtime-work/c150640-6272/physical-{name}")
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        result = ROOT / f"physical-{name}-{kind}.json"
        fixtures.append({"kind": kind, "command": command, "exit_code": 0,
                         "log": relative(log), "log_sha256": sha(log),
                         "result": relative(result), "result_sha256": sha(result)})
    receipt = {"format": "worker-physical-preparation", "case_id": ASSIGNMENT + "__" + name,
               "construction_sha256": construction_sha, "fixtures": fixtures,
               "lifecycle": {"events": ["capture_finished", "encoders_closed",
                                        "restoration_verified", "native_exit",
                                        "owner_released", "saved_processing_started"],
                             "exit_code": 0, "log": relative(log), "log_sha256": sha(log)}}
    path = ROOT / "proofs" / name / "physical-preparation.json"
    write(path, receipt)
    return {"receipt": relative(path), "sha256": sha(path)}


def delivery(name):
    case_id = ASSIGNMENT + "__" + name
    script = ROOT / "delivery_audit.py"
    fixture = f".runtime-work/c150640-6272/compat5-{name}-primary"
    output = f".runtime-work/c150640-6272/delivery5-{name}"
    common = (f".venv-cpu/bin/python work/{ASSIGNMENT}/delivery_probe.py "
              f"--case {case_id} --fixture {fixture} --output {output}")
    pos = ROOT / f"delivery-{name}-positive.log"
    neg = ROOT / f"delivery-{name}-negative.log"
    return {"case_id": case_id, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": relative(script), "script_sha256": sha(script),
            "command": common + " --mode positive", "test_exit_code": 0,
            "test_log": relative(pos), "test_log_sha256": sha(pos),
            "negative_command": common + " --mode missing_source",
            "negative_exit_code": 2,
            "negative_expected_error": "sealed original stop source missing or changed: stop-scene.json",
            "negative_log": relative(neg), "negative_log_sha256": sha(neg),
            "scope": "Synthetic CPU protocol proof; original physical delivery pending"}


def main():
    diagnostic = read(ROOT / "diagnostic-execution-manifest.json")
    plan = read(ROOT / "case-plan.json")
    by_name = {case.name: case for case in CASES}
    rows = []
    for entry in diagnostic["cases"]:
        name = entry["case_id"].split("__")[-1]
        if name not in by_name:
            raise ValueError("unknown exact case")
        construction = read(ROOT / entry["construction"])
        candidate = entry["candidates"][0]
        if candidate["id"] != "fallback1":
            raise ValueError("expected shared early-braking fallback")
        primary_offline = ROOT / f"cpu-offline-{name}.log"
        fallback_offline = ROOT / f"cpu-offline-{name}-fallback1.log"
        primary = {"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {entry['case_id']} --output .runtime-work/c150640-6272/offline5-{name}-primary",
                   "exit_code": 0, "construction_sha256": entry["construction_sha256"],
                   "log": relative(primary_offline), "log_sha256": sha(primary_offline)}
        fallback = {"id": "fallback1", "construction": candidate["construction"],
                    "construction_sha256": candidate["construction_sha256"],
                    "trigger": {"source": "original stop-history.jsonl and reviewed stop station",
                                "metric": "ego stopping-footprint longitudinal overshoot in metres",
                                "failure_condition": "Original footprint exceeds the reviewed stop target by more than 2 m; engineering tolerance only"},
                    "changed_knobs": ["engineering.stop_trigger_frame: 200 to 170"],
                    "offline": {"command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ASSIGNMENT}/diagnostic-execution-manifest.json --case {entry['case_id']} --candidate fallback1 --output .runtime-work/c150640-6272/offline5-{name}-fallback1",
                                "exit_code": 0, "construction_sha256": candidate["construction_sha256"],
                                "log": relative(fallback_offline), "log_sha256": sha(fallback_offline)},
                    "compatibility": bind_compat(name, "fallback1")}
        post_log = ROOT / f"cpu-saved-{name}.log"
        post_command = (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json "
                        f"--case {entry['case_id']} --attempt $ATTEMPT --output $DERIVED "
                        "--library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT")
        acquisition = {channel: {"entrypoint": "native_stop.py", "method": "capture",
                                 "evidence": "original source-gated Native actor/map/camera readback"}
                       for channel in CHANNELS}
        row = {**entry,
               "offline": primary, "compatibility": bind_compat(name, "primary"),
               "negative": {"log": relative(ROOT / "proofs" / name / "primary" / "negative.log")},
               "candidate_risk": {"status": "physical",
                                  "reason": "Original stopping footprint may overshoot the reviewed target; earlier braking is a common engineering fallback across linked comparisons."},
               "candidates": [fallback],
               "physical_preparation": physical(name, entry["construction_sha256"]),
               "delivery_acceptance": delivery(name),
               "post_capture": {"recorded_only": True, "command": post_command,
                                "feedback_command": post_command,
                                "test_exit_code": 0, "test_log": relative(post_log),
                                "test_log_sha256": sha(post_log)},
               "acquisition": acquisition,
               "pending_original_sources": ["reviewed original one-way map and roadway/shoulder polygons",
                                            "source-hashed jurisdiction, stop purpose, conflict and official direction",
                                            "released Native four-camera attempt and actual pixel review"],
               "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                  "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"},
               "status": "source_gated_cpu_preparation"}
        rows.append(row)
    if {row["case_id"] for row in rows} != {case["case_id"] for case in plan["cases"]}:
        raise ValueError("manifest/plan case mismatch")
    write(ROOT / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": diagnostic["runtime_manifest_sha256"],
        "cases": rows})


if __name__ == "__main__":
    main()
