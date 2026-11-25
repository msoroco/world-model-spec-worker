"""Build source-bound selected CPU diagnostics for the traffic-response pair."""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / "native/zone"
ASSIGNMENT = HERE.name
SOURCE_FIXTURE = HERE / "selected-probe1-fixture"
SOURCE_CONSTRUCTION = HERE / "selected-probe1-construction.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def put_rows(path, values):
    path.write_text("".join(json.dumps(value, sort_keys=True, allow_nan=False) + "\n"
                            for value in values))


def traffic_finalize(source, case_id):
    source = source.replace("__probe_1", "__traffic_" + case_id.split("__traffic_")[-1])
    source = source.replace("measure_adjoining_crossing", "measure_traffic_response")
    source = source.replace('"adjoining_crossing"', '"traffic_response"')
    source = source.replace('"zone_designation_verified": False,',
                            '"following_speed_drop_mps": metric["following_speed_drop_mps"],\n'
                            '            "zone_designation_verified": False,')
    marker = "    source_hashes = {name: sha(attempt / name) for name in SOURCES}"
    addition = '''    raw_rows = [json.loads(line) for line in
                (attempt / "native-raw-actors.jsonl").read_text().splitlines()]
    crossing = metric["first_observed_stripe_frame"]
    if crossing is None or crossing < 40 or crossing + 60 >= len(raw_rows):
        raise ValueError("Traffic response source windows unavailable")
    speeds = [row["following"]["speed_mps"] for row in raw_rows]
    metric["following_speed_drop_mps"] = round(
        sum(speeds[crossing - 40:crossing]) / 40 -
        min(speeds[crossing + 20:crossing + 60]), 5)
'''
    if marker not in source:
        raise ValueError("Selected finalizer source changed")
    return source.replace(marker, addition + marker)


def build(condition):
    if condition not in ("clear_traffic", "following_brake"):
        raise ValueError("Unknown exact traffic condition")
    prefix = "selected-traffic-" + condition
    case_id = ASSIGNMENT + "__traffic_" + condition
    dest = HERE / (prefix + "-fixture")
    dest.mkdir(exist_ok=True)
    for source in SOURCE_FIXTURE.rglob("*"):
        if source.is_file():
            target = dest / source.relative_to(SOURCE_FIXTURE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    raw = rows(dest / "native-raw-actors.jsonl")
    evidence = rows(dest / "capture/evidence.jsonl")
    previous_x = None
    for index, (row, item) in enumerate(zip(raw, evidence)):
        speed = 1 if condition == "following_brake" and index >= 172 else 2
        actor = row["following"]
        old_x = actor["center_native_xyz_m"][0]
        x = old_x if previous_x is None or speed == 2 else round(previous_x + speed / 20, 6)
        dx = x - old_x
        actor["center_native_xyz_m"][0] = x
        actor["velocity_native_xyz_mps"] = [speed, 0, 0]
        actor["speed_mps"] = speed
        for vertex in actor["body_native_xyz_m"]:
            vertex[0] = round(vertex[0] + dx, 6)
        item["participants"]["following"] = copy.deepcopy(actor)
        row["requested_following_speed_mps"] = speed
        previous_x = x
    put_rows(dest / "native-raw-actors.jsonl", raw)
    put_rows(dest / "capture/evidence.jsonl", evidence)
    review = json.loads((dest / "review.json").read_text())
    review["case_id"] = case_id
    review["raw_sha256"] = sha(dest / "native-raw-actors.jsonl")
    put(dest / "review.json", review)
    spec = HERE / "selected-probe1-fixture-spec.json"
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": str(path.relative_to(dest)),
                           "source": str(path.relative_to(ROOT)), "sha256": sha(path)}
                          for path in sorted(dest.rglob("*")) if path.is_file()],
              "generator": {"source": str(spec.relative_to(ROOT)), "sha256": sha(spec)}}
    road = ZONE / "drafts/probe_1/primary/zone-adjoining.xodr"
    recipe["sources"].append({"path": "road.xodr", "source": str(road.relative_to(ROOT)),
                              "sha256": sha(road)})
    recipe_path = HERE / (prefix + "-fixture-recipe.json")
    put(recipe_path, recipe)

    construction = json.loads(SOURCE_CONSTRUCTION.read_text())
    construction["case_id"] = case_id
    construction["status"] = "selected_traffic_diagnostic_pending_proofs"
    description = copy.deepcopy(construction["recording_description"])
    description["channels"].append({"name": "following_speed_response", "unit": "m/s",
                                    "method": "Native following-actor speed around stripe-body crossing",
                                    "reference_frame": "original Native frame and time",
                                    "sampling_rate_hz": 20, "time_window": "600-frame crossing attempt",
                                    "uncertainty": "50 ms bracket; physical cause pending"})
    construction["recording_description"] = description
    tracks = [json.loads(line) for line in next(item["content"] for item in construction["files"]
                                               if item["path"] == "requested-tracks.jsonl").splitlines()]
    for index, row in enumerate(tracks):
        row["case_suffix"] = "traffic_" + condition
        row["requested_following_speed_mps"] = 1 if condition == "following_brake" and index >= 172 else 2
    track_text = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in tracks)
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    cfg = json.loads(next(item["content"] for item in construction["files"]
                          if item["path"] == "config.json"))
    cfg.update({"case_id": case_id, "selected_case_id": case_id,
                "supported_case_ids": [case_id], "case": {"case_id": case_id},
                "traffic_policy": "traffic_" + condition,
                "case_plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
                "tracks_sha256": hashlib.sha256(track_text.encode()).hexdigest(),
                "recording_description": description})
    capture_helper = '''def traffic_following_target_speed(request):
    speed = request.get("requested_following_speed_mps")
    if speed not in (1, 2):
        raise ValueError("Traffic following speed request differs")
    return speed


'''
    for item in construction["files"]:
        path = item["path"]
        if path == "case-plan.json":
            item["content"] = plan_bytes.decode()
        elif path == "config.json":
            item["content"] = json.dumps(cfg, indent=2, allow_nan=False) + "\n"
        elif path == "requested-tracks.jsonl":
            item["content"] = track_text
        elif path == "check.py":
            item["content"] = (ZONE / "traffic_check.py").read_text()
        elif path == "capture.py":
            old = 'following.set_target_velocity(carla.Vector3D(x=2, y=0, z=0))'
            if item["content"].count(old) != 1:
                raise ValueError("Traffic capture controller source changed")
            item["content"] = item["content"].replace(
                "def capture(bundle, output, host, port):", capture_helper + "def capture(bundle, output, host, port):")
            item["content"] = item["content"].replace(
                old, 'following.set_target_velocity(carla.Vector3D(x=traffic_following_target_speed(request), y=0, z=0))')
        elif path == "finalize.py":
            item["content"] = traffic_finalize(item["content"], case_id)
        elif path == "tests/test_exact.py":
            item["content"] = '''import unittest
from pathlib import Path
from check import check
from capture import traffic_following_target_speed

class ExactTraffic(unittest.TestCase):
    def test_source_and_requested_crossing(self):
        row = check(Path.cwd())
        self.assertEqual(row["requested_crossing_frame"], 172)
        self.assertFalse(row["physical_crossing_observed"])
    def test_following_speed_controls(self):
        self.assertEqual(traffic_following_target_speed({"requested_following_speed_mps": 2}), 2)
        self.assertEqual(traffic_following_target_speed({"requested_following_speed_mps": 1}), 1)
    def test_invalid_speed_rejected(self):
        with self.assertRaises(ValueError):
            traffic_following_target_speed({"requested_following_speed_mps": 9})
'''
        elif path == "measurement-contract.json":
            contract = json.loads(item["content"])
            contract["case_id"] = case_id
            item["content"] = json.dumps(contract, indent=2, allow_nan=False) + "\n"
    construction_path = HERE / (prefix + "-construction.json")
    put(construction_path, construction)
    plan = json.loads(plan_bytes)
    disposition = plan["requirement_dispositions"][3]
    contract = {"format": "worker-measurement-contract", "case_id": case_id,
                "requirements": [{"disposition_index": 3,
                                  "requirement": disposition["requirement"],
                                  "source": disposition["source"],
                                  "kind": "measured", "method": "measure_traffic_response",
                                  "output_key": "traffic_response", "value_type": "object",
                                  "inputs": ["native-raw-actors.jsonl", "video_frames.jsonl",
                                             "review.json", "trace.jsonl", "capture/evidence.jsonl"]}],
                "negative": {"remove": ["native-raw-actors.jsonl"],
                             "error_contains": "Missing required source: native-raw-actors.jsonl"},
                "status": "selected_traffic_diagnostic_pending_proofs"}
    contract_path = HERE / (prefix + "-measurement-contract.json")
    put(contract_path, contract)
    manifest = {"format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
                "runtime_manifest_sha256": json.loads((HERE / "selected-probe1-manifest.json").read_text())["runtime_manifest_sha256"],
                "status": "selected_traffic_diagnostic_pending_proofs", "delivery_ready": False,
                "original_native_observed": False,
                "cases": [{"case_id": case_id, "id": "primary", "kind": "delivery",
                           "construction": construction_path.name,
                           "construction_sha256": sha(construction_path), "candidates": [],
                           "fixture_recipe": str(recipe_path.relative_to(ROOT)),
                           "measurement_contract": contract_path.name,
                           "measurement_procedure": {"entrypoint": "finalize.py"}}]}
    put(HERE / (prefix + "-manifest.json"), manifest)
    proposal_path = HERE / "proposals/cases.json"
    proposal = json.loads(proposal_path.read_text())
    cases = {item["case_id"]: item for item in proposal["cases"]}
    cases[case_id] = {"case_id": case_id, "recording_description": description}
    proposal["cases"] = [cases[key] for key in sorted(cases)]
    put(proposal_path, proposal)
    return {"case_id": case_id, "construction_sha256": sha(construction_path),
            "manifest_sha256": sha(HERE / (prefix + "-manifest.json"))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=("clear_traffic", "following_brake"), required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.condition)))
