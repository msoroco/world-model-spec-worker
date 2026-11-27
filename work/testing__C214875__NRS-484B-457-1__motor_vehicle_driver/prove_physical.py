"""Replay synthetic original wheel/frame/camera evidence for three outcomes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from curb_geometry import SOURCES, ASSIGNMENT
from native_acquisition import capture
from audit_original_attempt import audit
from test_native_acquisition import FakeOperator

ROOT = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fixture(case_id, kind):
    variant = case_id.rsplit("__", 1)[1]
    target = 19 if "19in" in variant else 17 if "17in" in variant else 18
    angle = 8 if "skew" in variant else 0
    parked = variant.startswith("park")
    scratch = Path(os.environ["TMPDIR"])
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c214875-physical-") as temporary:
        root = Path(temporary)
        map_bytes = b"synthetic diagnostic OpenDRIVE identity; no public-road assertion"
        sources = {}
        for name in SOURCES:
            data = map_bytes if name == "native_opendrive_map" else ("diagnostic:" + name).encode()
            path = root / (name + ".source")
            path.write_bytes(data)
            sources[name] = {"path": path.name, "sha256": sha(path)}
        site = root / "site.json"
        write(site, {"format": "worker-right-curb-site-v1", "case_id": case_id,
                     "sources": sources,
                     "reviewed_assertions": {"public_highway": True,
                                             "residence_district": True,
                                             "adjacent_right_curb": True,
                                             "ordinary_motor_vehicle": True,
                                             "right_side_default_branch": True,
                                             "left_curb_ordinance_applies": False,
                                             "angle_parking_ordinance_applies": False},
                     "right_curb_xy_m": [[-10, 0], [10, 0]],
                     "parking_route_xy_m": [[-8, 1], [8, 1]],
                     "roadway_side_of_curb": "left",
                     "reviewed_right_wheel_axle_spacing_m": 2.7,
                     "reviewed_curb_station_m": 8})

        class Interrupted(FakeOperator):
            def read_right_wheels(self, frame):
                value = super().read_right_wheels(frame)
                if self.index >= 800:
                    value["speed_mps"] = 2.0
                return value

        operator = (Interrupted if kind == "incomplete_motion" else FakeOperator)(
            map_bytes, distance_inches=target, angle_deg=angle, parked=parked)
        attempt = root / "attempt"
        capture(operator, site, case_id, attempt, diagnostic=True, diagnostic_full_duration=True)
        motion = attempt / "original-attempt" / "wheel-motion.jsonl"
        if kind == "missing_evidence":
            motion.unlink()
        missing = []
        if not motion.is_file():
            missing.append("original-attempt/wheel-motion.jsonl")
            observed = {}
            status = "unverified"
            sources_used = {"site.json": sha(site)}
        else:
            checked = audit(attempt, case_id)
            measured = checked["measurement"]
            stopped = len(measured["stopped_frames"])
            activity = len(measured["parking_brake_frames"] if parked else measured["stopped_without_parking_brake_frames"])
            observed = {"original_frame_count": checked["frame_count"],
                        "stopped_frames": stopped, "activity_frames": activity,
                        "max_right_wheel_distance_inches": measured["max_right_wheel_distance_inches"],
                        "max_wheel_curb_alignment_deg": measured["max_wheel_curb_alignment_deg"]}
            sources_used = measured["source_hashes"]
            met = (stopped == 900 and activity == 900 and
                   abs(observed["max_right_wheel_distance_inches"] - target) <= .01 and
                   abs(observed["max_wheel_curb_alignment_deg"] - angle) <= .01)
            status = "met" if met else "not_met"
        if kind == "complete_motion" and status != "met":
            raise ValueError("full-duration synthetic curb activity did not complete")
        if kind == "incomplete_motion" and status != "not_met":
            raise ValueError("interrupted synthetic curb activity was accepted")
        if kind == "missing_evidence" and status != "unverified":
            raise ValueError("missing source was accepted")
        return {"case_id": case_id, "provenance_kind": "synthetic_fixture",
                "diagnostic_fixture": True, "maneuver_completed": status == "met",
                "realized_observables": observed,
                "physical_checks": {"maneuver": {"status": status,
                    "method": "source-sealed 900-frame original wheel, activity and four-camera diagnostic replay",
                    "sources": sources_used, "missing_evidence": missing,
                    "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}}}


def build():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.rsplit("__", 1)[1]
        folder = ROOT / "cases" / variant
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            command = [sys.executable, str(ROOT / "prove_physical.py"),
                       "--case", case_id, "--kind", kind]
            process = subprocess.run(command, env=os.environ.copy(), text=True,
                                     capture_output=True)
            if process.returncode:
                raise ValueError(process.stdout + process.stderr)
            result = json.loads(process.stdout)
            result_path = folder / ("physical-" + kind + "-result.json")
            log_path = folder / ("physical-" + kind + ".log")
            write(result_path, result)
            log_path.write_text(process.stdout.rstrip() + "\n")
            fixtures.append({"kind": kind,
                             "command": ".venv-cpu/bin/python work/" + ASSIGNMENT +
                                        "/prove_physical.py --case " + case_id + " --kind " + kind,
                             "exit_code": 0,
                             "result": str(result_path.relative_to(ROOT)),
                             "result_sha256": sha(result_path),
                             "log": str(log_path.relative_to(ROOT)),
                             "log_sha256": sha(log_path)})
        lifecycle_log = folder / "physical-lifecycle.log"
        lifecycle_log.write_text("Synthetic capture joined and owner cleanup confirmed before saved processing.\n"
                                 + " -> ".join(EVENTS) + "\n")
        receipt = folder / "physical-preparation.json"
        write(receipt, {"construction_sha256": entry["construction_sha256"],
                        "fixtures": fixtures,
                        "lifecycle": {"events": EVENTS, "exit_code": 0,
                                      "log": str(lifecycle_log.relative_to(ROOT)),
                                      "log_sha256": sha(lifecycle_log)}})
        entry["physical_preparation"] = {"receipt": str(receipt.relative_to(ROOT)),
                                         "sha256": sha(receipt)}
    write(manifest_path, manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--kind")
    args = parser.parse_args()
    if args.case and args.kind:
        if not args.case.startswith(ASSIGNMENT + "__"):
            raise ValueError("wrong case")
        print(json.dumps(fixture(args.case, args.kind), sort_keys=True))
    else:
        build()
        print("five source-bound physical diagnostic receipts built")
