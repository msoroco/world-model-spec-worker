"""Build exact source-gated hose constructions for pinned CPU offline checks."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
SOURCE_NAMES = ("fire_hose_delivery.py", "delivery_audit.py", "native_capture.py")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")

RUNNER = '''"""Exact hose entrypoint; original reviewed sources are mandatory for capture."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from fire_hose_delivery import segment_intersects, Point
from native_capture import capture


def check(root):
    config = json.loads((root / "config.json").read_text())
    case = config["case"]
    if config["selected_case_id"] != config["assignment_id"] + "__" + case["short_id"]:
        raise ValueError("exact hose case identity differs")
    if (config["law_id"], config["cell_id"], config["actor"]) != (
            "NRS-484B-913", "C197786", "motor_vehicle_driver"):
        raise ValueError("hose law/cell/actor identity differs")
    if (config["frame_count"], config["rate_hz"], config["duration_s"]) != (900, 20, 45):
        raise ValueError("Native capture profile differs")
    if set(config["camera_views"]) != {"overview", "approach", "reference_corner", "driver_reference"}:
        raise ValueError("four camera source views differ")
    if case["incident_purpose"] not in ("fire", "alarm", "practice"):
        raise ValueError("qualifying hose incident purpose differs")
    if case["hose_protection"] not in ("unprotected", "protected"):
        raise ValueError("hose protection case differs")
    if case["command_consent"] not in ("none", "given", "withheld"):
        raise ValueError("command consent case differs")
    if config["source_gate"] != "reviewed_original_required":
        raise ValueError("reviewed original source gate differs")
    return config


def reviewed_source(packet_path, source_root, config):
    packet_path = Path(packet_path)
    root = Path(source_root).resolve()
    packet = json.loads(packet_path.read_text())
    if packet.get("case_id") != config["selected_case_id"]:
        raise ValueError("reviewed packet exact case differs")
    if (packet.get("cell_id"), packet.get("law_id")) != ("C197786", "NRS-484B-913"):
        raise ValueError("reviewed packet law/cell differs")
    source_paths = set()
    for key in ("private_way", "hose", "incident", "official", "consent", "vehicle"):
        source = packet.get(key)
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise ValueError(key + " reviewed original source missing")
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(key + " reviewed original file unavailable")
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(key + " reviewed original hash mismatch")
        if path in source_paths:
            raise ValueError("distinct reviewed original sources required")
        source_paths.add(path)
        original = json.loads(path.read_text())
        expected = {field: value for field, value in source.items() if field not in ("path", "sha256")}
        if original != expected:
            raise ValueError(key + " reviewed original content mismatch")
    hose = packet["hose"]
    if hose.get("fire_department_affiliation") is not True:
        raise ValueError("fire-department hose affiliation unproven")
    if not hose.get("blueprint_id") or "hose" not in hose["blueprint_id"].lower():
        raise ValueError("hose-specific blueprint identity missing")
    if hose.get("protection") != config["case"]["hose_protection"]:
        raise ValueError("hose protection source differs")
    if packet["incident"].get("purpose") != config["case"]["incident_purpose"]:
        raise ValueError("incident purpose source differs")
    if packet["consent"].get("status") != config["case"]["command_consent"]:
        raise ValueError("official consent source differs")
    if not packet["official"].get("in_command") or not packet["official"].get("identity"):
        raise ValueError("command official source unproven")
    if packet["consent"].get("status") == "given" and (
            packet["consent"].get("official_identity") != packet["official"]["identity"]
            or packet["consent"].get("frame") is None or not packet["consent"].get("scope")):
        raise ValueError("command official consent timing or scope unproven")
    if packet["vehicle"].get("ordinary_motor_vehicle") is not True or packet["vehicle"].get("human_driver") is not True:
        raise ValueError("vehicle and human driver source unproven")
    road = packet["private_way"]
    if not road.get("owner") or not road.get("permitted_access"):
        raise ValueError("private way ownership or access unproven")
    path = road.get("ego_route_xy")
    segment = hose.get("segment_xy")
    if not isinstance(path, list) or len(path) < 2 or not isinstance(segment, list) or len(segment) != 2:
        raise ValueError("reviewed route or actual hose segment missing")
    crosses = any(segment_intersects(Point(*a), Point(*b), Point(*segment[0]), Point(*segment[1]))
                  for a, b in zip(path, path[1:]))
    if crosses != config["case"]["planned_hose_crossing"]:
        raise ValueError("reviewed route/hose geometry differs from exact case")
    return packet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--reviewed-packet", type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    config = check(Path(__file__).resolve().parent)
    if args.check:
        print(config["selected_case_id"])
        return
    packet_path = args.reviewed_packet or os.environ.get("HOSE_REVIEWED_PACKET")
    source_root = args.source_root or os.environ.get("HOSE_SOURCE_ROOT")
    if not packet_path or not source_root or not args.output_dir or not args.host or not args.port:
        raise ValueError("original reviewed packet, source root, Native server and output required")
    packet = reviewed_source(packet_path, source_root, config)
    adapter_name = os.environ.get("HOSE_NATIVE_ADAPTER")
    if not adapter_name:
        raise ValueError("reviewed Native hose capture adapter required")
    adapter = importlib.import_module(adapter_name).create_adapter(config, args.host, args.port)
    if adapter.provenance() != "original_native":
        raise ValueError("original Native adapter provenance required")
    print(json.dumps(capture(adapter, config, packet, packet_path, source_root, args.output_dir),
                     sort_keys=True))


if __name__ == "__main__":
    main()
'''

TEST = '''import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from runner import check, reviewed_source


class ExactHoseBundleTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]
        self.config = check(self.root)

    def test_exact_identity_and_source_gate(self):
        self.assertEqual(self.config["selected_case_id"],
                         self.config["assignment_id"] + "__" + self.config["case"]["short_id"])
        self.assertEqual(self.config["source_gate"], "reviewed_original_required")

    def test_missing_reviewed_packet_rejected(self):
        with self.assertRaises(FileNotFoundError):
            reviewed_source(self.root / "unavailable-original.json", self.root, self.config)

    def test_changed_case_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as temp:
            root = Path(temp)
            changed = dict(self.config)
            changed["selected_case_id"] += "-changed"
            (root / "config.json").write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, "exact hose case identity differs"):
                check(root)

    def test_reviewed_geometry_and_source_hashes(self):
        with tempfile.TemporaryDirectory(dir=os.environ["HOSE_SCRATCH_ROOT"]) as temp:
            root = Path(temp)
            binding = {"path": "pending.json", "sha256": "0" * 64}
            packet = {"case_id": self.config["selected_case_id"], "cell_id": "C197786",
                      "law_id": "NRS-484B-913", "private_way": dict(binding, owner="owner",
                      permitted_access=["owner"], ego_route_xy=[[0, -1], [0, 1]]),
                      "hose": dict(binding, fire_department_affiliation=True,
                      blueprint_id="static.prop.firehose", protection=self.config["case"]["hose_protection"],
                      segment_xy=[[-1, 0], [1, 0]]),
                      "incident": dict(binding, purpose=self.config["case"]["incident_purpose"]),
                      "official": dict(binding, in_command=True, identity="captain"),
                      "consent": dict(binding, status=self.config["case"]["command_consent"]),
                      "vehicle": dict(binding, ordinary_motor_vehicle=True, human_driver=True)}
            if packet["consent"]["status"] == "given":
                packet["consent"].update(official_identity="captain", frame=20, scope="hose crossing")
            if not self.config["case"]["planned_hose_crossing"]:
                packet["private_way"]["ego_route_xy"] = [[2, -1], [2, 1]]
            for key in ("private_way", "hose", "incident", "official", "consent", "vehicle"):
                source = root / (key + ".json")
                original = {field: value for field, value in packet[key].items()
                            if field not in ("path", "sha256")}
                source.write_text(json.dumps(original, sort_keys=True) + "\\n")
                packet[key]["path"] = source.name
                packet[key]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            path = root / "packet.json"
            path.write_text(json.dumps(packet))
            self.assertEqual(reviewed_source(path, root, self.config)["case_id"],
                             self.config["selected_case_id"])
            packet["hose"]["sha256"] = "0" * 64
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "hose reviewed original hash mismatch"):
                reviewed_source(path, root, self.config)
            packet["hose"]["sha256"] = hashlib.sha256((root / "hose.json").read_bytes()).hexdigest()
            packet["private_way"]["ego_route_xy"] = ([[2, -1], [2, 1]]
                                                         if self.config["case"]["planned_hose_crossing"]
                                                         else [[0, -1], [0, 1]])
            path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "content mismatch"):
                reviewed_source(path, root, self.config)
'''


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    semantic_path = ROOT / "proposals" / "cases.json"
    semantic_cases = ({case["case_id"]: case for case in json.loads(semantic_path.read_text())["cases"]}
                      if semantic_path.is_file() else {})
    manifest_cases = []
    for item in plan["cases"]:
        short_id = item["case_id"].removeprefix(ASSIGNMENT + "__")
        config = {
            "assignment_id": ASSIGNMENT,
            "selected_case_id": item["case_id"],
            "cell_id": "C197786", "law_id": "NRS-484B-913", "actor": "motor_vehicle_driver",
            "frame_count": 900, "rate_hz": 20, "duration_s": 45,
            "camera_views": list(CAMERAS),
            "camera_dimensions": {name: ([1920, 1080] if name == "overview" else [1280, 720])
                                  for name in CAMERAS},
            "cameras": [{"name": name,
                         "width": 1920 if name == "overview" else 1280,
                         "height": 1080 if name == "overview" else 720} for name in CAMERAS],
            "required_atoms": [], "source_packets": [], "source_gate": "reviewed_original_required",
            "case": {"short_id": short_id,
                     "incident_purpose": item["incident_purpose"],
                     "hose_protection": item["hose_protection"],
                     "command_consent": item["command_consent"],
                     "planned_hose_crossing": item["planned_hose_crossing"]},
        }
        files = [{"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
                 {"path": "runner.py", "content": RUNNER},
                 {"path": "tests/test_bundle.py", "content": TEST}]
        files += [{"path": name, "content": (ROOT / name).read_text()} for name in SOURCE_NAMES]
        construction = {
            "case_id": item["case_id"], "cell_id": "C197786", "law_id": "NRS-484B-913",
            "actor": "motor_vehicle_driver", "entrypoint": "runner.py", "files": files,
            "diagnostic_only": True, "physical_acceptance_claimed": False, "legal_judgment": None,
        }
        if item["case_id"] in semantic_cases:
            construction["recording_description"] = semantic_cases[item["case_id"]]["recording_description"]
        path = ROOT / "cases" / short_id / "construction.json"
        write_json(path, construction)
        manifest_cases.append({
            "case_id": item["case_id"], "construction": str(path.relative_to(ROOT)),
            "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "diagnostic_only": True,
            "candidate_risk": item["candidate_risk"],
        })
    write_json(ROOT / "diagnostic-execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "diagnostic_only": True, "cases": manifest_cases,
        "comparisons": [x["comparison_id"] for x in plan["comparisons"]],
    })
    print(json.dumps({"exact_cases": len(manifest_cases), "diagnostic_only": True}))


if __name__ == "__main__":
    build()
