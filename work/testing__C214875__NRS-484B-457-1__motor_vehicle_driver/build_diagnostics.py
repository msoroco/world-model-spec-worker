"""Inventory nine-frame synthetic Native source joins for CPU compatibility."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

from curb_geometry import ASSIGNMENT, SOURCES
from native_acquisition import CAMERAS, capture
from test_native_acquisition import FakeOperator

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TEMPLATE = REPO / "work/testing__C233871__NRS-484B-280-1c__motor_vehicle_driver/diagnostic-prompt_brake.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build():
    template = json.loads(TEMPLATE.read_text())
    frames = [json.loads(line) for line in template["files"]["video_frames.jsonl"].splitlines()]
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        variant = case_id.rsplit("__", 1)[1]
        target = 19 if "19in" in variant else 17 if "17in" in variant else 18
        angle = 8 if "skew" in variant else 0
        parked = variant.startswith("park")
        folder = ROOT / "diagnostics" / variant
        folder.mkdir(parents=True, exist_ok=True)
        scratch = Path(os.environ["TMPDIR"])
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c214875-fixture-") as temporary:
            temp = Path(temporary)
            map_bytes = template["files"]["road.xodr"].encode()
            sources = {}
            for name in SOURCES:
                data = map_bytes if name == "native_opendrive_map" else ("diagnostic:" + name).encode()
                path = temp / (name + ".source")
                path.write_bytes(data)
                sources[name] = {"path": path.name, "sha256": sha(path)}
            site = temp / "site.json"
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

            class MatchedOperator(FakeOperator):
                def tick(self):
                    self.index += 1
                    return {"frame": frames[self.index]["carla_frame"],
                            "time_s": frames[self.index]["time_s"]}

                def read_right_wheels(self, frame):
                    row = super().read_right_wheels(100 + self.index)
                    row.update(frame=frame, time_s=frames[self.index]["time_s"])
                    return row

                def read_cameras(self, frame):
                    packets = super().read_cameras(100 + self.index)
                    for item in packets.values():
                        item.update(frame=frame, time_s=frames[self.index]["time_s"])
                    return packets

            attempt = temp / "attempt"
            capture(MatchedOperator(map_bytes, distance_inches=target, angle_deg=angle,
                                    parked=parked), site, case_id, attempt, diagnostic=True)
            original = attempt / "original-attempt"
            inventory_path = original / "inventory.json"
            inventory = json.loads(inventory_path.read_text())
            ledgers = {}
            for name in CAMERAS:
                archive = original / (name + ".zip")
                with zipfile.ZipFile(archive) as zipped:
                    names = zipped.namelist()
                    rows = [{"frame": index, "native_frame": frames[index]["carla_frame"],
                             "png_sha256": hashlib.sha256(zipped.read(filename)).hexdigest()}
                            for index, filename in enumerate(names)]
                archive.unlink()
                path = original / (name + ".frames.json")
                write(path, rows)
                ledgers[name] = sha(path)
            inventory.pop("camera_sha256")
            inventory["diagnostic_camera_ledgers_sha256"] = ledgers
            write(inventory_path, inventory)
            sources_list = []
            for path in sorted(original.iterdir()):
                if not path.is_file():
                    raise ValueError("unexpected diagnostic source directory")
                target = folder / "original-attempt" / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                sources_list.append({"path": "original-attempt/" + path.name,
                                     "source": str(target.relative_to(REPO)),
                                     "sha256": sha(target)})
        specification = {"files": {key: value for key, value in template["files"].items()
                                   if key in ("trace.jsonl", "video_frames.jsonl", "road.xodr",
                                              "fixture-provenance.json") or key.startswith("capture/")},
                         "graphs": template["graphs"], "videos": template["videos"]}
        captured_manifest = json.loads(specification["files"]["capture/manifest.json"])
        captured_manifest["case_id"] = case_id
        specification["files"]["capture/manifest.json"] = json.dumps(captured_manifest, sort_keys=True) + "\n"
        provenance = {"scope": "CPU synthetic right-curb diagnostic only",
                      "case_id": case_id, "physical_acceptance_claimed": False,
                      "generic_graph_visualization": True}
        specification["files"]["fixture-provenance.json"] = json.dumps(provenance, sort_keys=True) + "\n"
        spec_path = folder / "diagnostic.json"
        spec_path.write_text(json.dumps(specification, separators=(",", ":"), sort_keys=True) + "\n")
        recipe_path = folder / "fixture-recipe.json"
        write(recipe_path, {"format": "worker-fixture-recipe", "sources": sources_list,
                            "generator": {"source": str(spec_path.relative_to(REPO)),
                                          "sha256": sha(spec_path)}})
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
    write(manifest_path, manifest)
    return len(plan["cases"])


if __name__ == "__main__":
    print(build())
