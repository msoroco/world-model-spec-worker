"""Create and check two 30-second, source-hashed CPU corridor diagnostics."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("assess_corridor", ROOT / "native" / "assess_corridor.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def make(folder, lead_y, ego_y):
    folder.mkdir(parents=True, exist_ok=True)
    write(folder / "geometry.json", {
        "coordinate_frame": "road_local_y_right_positive", "paved_y_m": [-4.0, 4.0],
        "right_shoulder_y_m": [4.0, 6.0], "right_shoulder_paved": False,
        "ego_width_m": 1.8, "ego_length_m": 4.5,
        "lead_width_m": 1.8, "lead_length_m": 4.5, "clearance_m": 0.2,
    })
    with (folder / "actors.jsonl").open("w") as stream:
        for i in range(600):
            row = {"frame": 1000 + i, "time_s": i / 20,
                   "actors": {"ego": {"x_m": i * 0.1, "y_m": ego_y},
                              "lead": {"x_m": 20 + i * 0.05, "y_m": lead_y}}}
            stream.write(json.dumps(row, sort_keys=True) + "\n")
    write(folder / "sources.json", {"kind": "synthetic_cpu_corridor",
                                    "sha256": {name: module.sha256(folder / name)
                                               for name in ("geometry.json", "actors.jsonl")}})


def reject(source, change, expected, rehash=True):
    with tempfile.TemporaryDirectory() as scratch:
        trial = Path(scratch)
        for name in ("geometry.json", "actors.jsonl", "sources.json"):
            (trial / name).write_bytes((source / name).read_bytes())
        change(trial)
        if rehash:
            manifest = json.loads((trial / "sources.json").read_text())
            for name in ("geometry.json", "actors.jsonl"):
                manifest["sha256"][name] = module.sha256(trial / name)
            write(trial / "sources.json", manifest)
        try:
            module.assess(trial)
        except ValueError as error:
            assert expected in str(error), str(error)
            return str(error)
        raise AssertionError("Corrupt diagnostic source was accepted")


def edit_row(folder, edit):
    path = folder / "actors.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    edit(rows)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


fixtures = ROOT / "fixtures" / "corridor"
make(fixtures / "paved_available", lead_y=0.5, ego_y=2.6)
make(fixtures / "paved_unavailable_local", lead_y=1.6, ego_y=4.2)
observed = {name: module.assess(fixtures / name)
            for name in ("paved_available", "paved_unavailable_local")}
assert observed["paved_available"]["paved_right_corridor_feasible_frames"] == 181
assert observed["paved_available"]["off_paved_during_right_pass_frames"] == 0
assert observed["paved_unavailable_local"]["paved_right_corridor_feasible_frames"] == 0
assert observed["paved_unavailable_local"]["off_paved_during_right_pass_frames"] == 181
assert observed["paved_available"]["right_pass_overlap_frames"] == observed["paved_unavailable_local"]["right_pass_overlap_frames"]
source = fixtures / "paved_unavailable_local"
negative = {
    "changed_hash": reject(source, lambda trial: edit_row(trial, lambda rows: rows[0]["actors"]["ego"].update({"y_m": 4.3})), "Source hash differs", False),
    "missing_lead": reject(source, lambda trial: edit_row(trial, lambda rows: rows[0]["actors"].pop("lead")), "Ego or lead source missing"),
    "frame_gap": reject(source, lambda trial: edit_row(trial, lambda rows: rows[0].update({"frame": 1002})), "Source frame/time join differs"),
    "unknown_shoulder": reject(source, lambda trial: write(trial / "geometry.json", dict(json.loads((trial / "geometry.json").read_text()), right_shoulder_paved=None)), "Shoulder paving status unknown"),
}
proof = {"format": "c178778-source-bound-corridor-diagnostic-v1", "selected": False,
         "accepted": False, "observed": observed, "negative_errors": negative,
         "controlled_diagnostic_changes": ["lead lateral location", "ego lateral route"],
         "limitations": ["synthetic CPU poses are not Native motion",
                         "a locally unavailable paved corridor does not establish that the complete movement requires leaving pavement",
                         "alternate timing, path, highway status and actual physical constraints remain untested",
                         "this diagnostic pair is not the final controlled statutory comparison"]}
path = ROOT / "corridor-proof.json"
write(path, proof)
print(json.dumps({"positives": 2, "negatives": len(negative),
                  "proof_sha256": module.sha256(path)}, sort_keys=True))
