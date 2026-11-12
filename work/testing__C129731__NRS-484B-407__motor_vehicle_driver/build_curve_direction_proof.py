"""Build a distinct curve sight-direction exact case from the authored road."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

from build_curve_opendrive import check_source_geometry, lane_position
from site_construction import validate_site

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBES = {"short_of_500ft": ("", ""), "at_500ft": ("-at", "-at"),
          "beyond_500ft": ("-beyond", "-beyond")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def body(vertices, old_center):
    center = lane_position(220 + old_center[0], -1)
    center[2] += old_center[2]
    return [[center[i] + v[i] - old_center[i] for i in range(3)] for v in vertices]


def ego(old):
    xyz = lane_position(220 + old[0], -1)
    xyz[2] += old[2]
    return xyz


def observation(obs):
    for participant in obs.get("participants", []):
        old = participant["position_m"]
        participant["body_vertices_m"] = body(participant["body_vertices_m"], old)
        participant["position_m"] = ego(old)


def visibility(vis, old_center, direction):
    center = ego(old_center)
    for sample in vis["ego_body_samples_m"]:
        sample[:] = [center[i] + sample[i] - old_center[i] for i in range(3)]
    approaches = vis["approaches"]
    if [a["lane_id"] for a in approaches] != [-1, 1]:
        raise ValueError("Expected source A/B visibility order")
    if direction == "approach_b":
        for row in approaches:
            row["lane_id"] *= -1
        approaches.reverse()


def transform_sources(base, dest, site, site_hash, road, case_id, direction):
    sources = {}
    for source in sorted(base.rglob("*")):
        if not source.is_file():
            continue
        name = source.relative_to(base).as_posix()
        target = dest / "sources" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if name in ("motion_history.jsonl", "turn_history.jsonl", "trace.jsonl",
                    "capture/evidence.jsonl"):
            rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
            if len(rows) != 1100:
                raise ValueError("Incomplete original diagnostic source: " + name)
            for row in rows:
                if name == "motion_history.jsonl":
                    row["site_source_sha256"] = site_hash
                    row["ego"]["location_xyz_m"] = ego(row["ego"]["location_xyz_m"])
                    for approach, actor in row["approaches"].items():
                        old = actor["location_xyz_m"]
                        lane = -1 if approach == "approach_a" else 1
                        actor["location_xyz_m"] = lane_position(220 + old[0], lane)
                elif name == "turn_history.jsonl":
                    vertices = row["body_vertices_m"]
                    old_center = [(min(v[i] for v in vertices) + max(v[i] for v in vertices)) / 2
                                  for i in range(3)]
                    row["body_vertices_m"] = body(vertices, old_center)
                elif name == "trace.jsonl":
                    xyz = ego(row["position_m"])
                    row["position_m"] = xyz
                    row["position"] = dict(zip(("x", "y", "z"), xyz))
                else:
                    old = row["ego"]["position_m"]
                    row["ego"]["body_vertices_m"] = body(row["ego"]["body_vertices_m"], old)
                    row["ego"]["position_m"] = ego(old)
                    observation(row["original_observations"])
                    visibility(row["visibility"], old, direction)
            target.write_text("".join(json.dumps(row, separators=(",", ":"), allow_nan=False) +
                                      "\n" for row in rows))
        elif name == "curve_context.json":
            packet = json.loads(source.read_text())
            packet.update({"site_source_sha256": site_hash, "turn_site_xyz_m": site["turn_site_xyz_m"],
                           "incoming_lanes": site["incoming_lanes"]})
            target.write_text(json.dumps(packet, separators=(",", ":")) + "\n")
        elif name == "road.xodr":
            target.write_bytes(road.read_bytes())
        elif name == "capture/manifest.json":
            packet = json.loads(source.read_text())
            packet["case_id"] = case_id
            target.write_text(json.dumps(packet, separators=(",", ":")) + "\n")
        else:
            target.write_bytes(source.read_bytes())
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Returned source exceeds 2 MiB: " + name)
        sources[name] = target
    capture = json.loads(sources["capture/manifest.json"].read_text())
    for name in ("road.xodr", "trace.jsonl"):
        capture["sources"][name] = sha(sources[name])
    sources["capture/manifest.json"].write_text(
        json.dumps(capture, separators=(",", ":")) + "\n")
    return sources


def build(probe, direction):
    suffix, base_suffix = PROBES[probe]
    short = {"short_of_500ft": "short", "at_500ft": "at",
             "beyond_500ft": "beyond"}[probe]
    name = "canonical-curve-" + short + "-" + ("a" if direction == "approach_a" else "b")
    case_id = HERE.name + "__curve__" + probe + "__occluded_" + direction
    dest = HERE / ("branch-proof-" + name)
    road = HERE / "native-map-plan/curve-road.xodr"
    source_site = HERE / "native-map-plan" / ("curve_" + probe + "__occluded_" + direction + ".json")
    site = validate_site(json.loads(source_site.read_text()))
    if site["source_status"] != "diagnostic_fixture" or site["occluder"]["target_direction"] != direction:
        raise ValueError("Wrong curve direction site")
    check_source_geometry(road.read_text(), site)
    site_name = "diagnostic-site" + suffix + ".json"
    site_path = dest / site_name
    site_path.parent.mkdir(parents=True, exist_ok=True)
    site_path.write_bytes(source_site.read_bytes())
    site_hash = sha(site_path)
    config = json.loads((HERE / ("config" + suffix + ".json")).read_text())
    config["selected_case_id"] = case_id
    config["supported_case_ids"] = list(dict.fromkeys(config["supported_case_ids"] + [case_id]))
    config["site_source"] = {"path": site_name, "sha256": site_hash}
    config_path = dest / "config.json"
    dump(config_path, config)
    base = HERE / ("diagnostic-sources" + base_suffix)
    sources = transform_sources(base, dest, site, site_hash, road, case_id, direction)
    spec = copy.deepcopy(json.loads((HERE / ("diagnostic" + suffix + ".json")).read_text()))
    for graph in spec["graphs"]:
        observed = graph["attributes"].get("observed_evidence")
        if observed:
            observation(observed)
    spec_path = dest / "diagnostic.json"
    spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    items = [{"path": key, "source": str(path.relative_to(ROOT)), "sha256": sha(path)}
             for key, path in sorted(sources.items())]
    items.append({"path": "diagnostic-input.json", "source": str(spec_path.relative_to(ROOT)),
                  "sha256": sha(spec_path)})
    dump(dest / "recipe.json", {"format": "worker-fixture-recipe", "sources": items,
                                "generator": {"source": str(spec_path.relative_to(ROOT)),
                                              "sha256": sha(spec_path)}})
    construction = copy.deepcopy(json.loads((HERE / ("construction" + suffix + ".json")).read_text()))
    construction["case_id"] = case_id
    marker = 'for probe in ("short_of_500ft", "at_500ft", "beyond_500ft")}\n'
    for file in construction["files"]:
        if file["path"] == "config.json":
            file["content"] = config_path.read_text()
            file["source"] = str(config_path.relative_to(ROOT))
        elif file["path"] == site_name:
            file["content"] = site_path.read_text()
            file["source"] = str(site_path.relative_to(ROOT))
        elif file["path"] == "runner.py":
            if file["content"].count(marker) != 1:
                raise ValueError("Cannot bind curve exact case in runner")
            file["content"] = file["content"].replace(
                marker, marker + "CASES[" + repr(case_id) + "] = ('curve', " + repr(probe) + ")\n")
            runner = dest / "runner.py"
            runner.write_text(file["content"])
            file["source"] = str(runner.relative_to(ROOT))
    construction["branch_engineering"] = {"occluded_direction": direction,
        "source_status": "diagnostic_fixture", "physical_acceptance_claimed": False}
    construction_path = dest / "construction.json"
    dump(construction_path, construction)
    manifest_name = "diagnostic-" + name + "-manifest.json"
    source_manifest = "diagnostic-execution-manifest.json" if not suffix else "diagnostic" + suffix + "-manifest.json"
    manifest = copy.deepcopy(json.loads((HERE / source_manifest).read_text()))
    entry = manifest["cases"][0]
    entry["case_id"] = case_id
    entry["construction"] = str(construction_path.relative_to(HERE))
    entry["construction_sha256"] = sha(construction_path)
    entry["fixture_recipe"] = str((dest / "recipe.json").relative_to(ROOT))
    dump(HERE / manifest_name, manifest)
    receipt = {"case_id": case_id, "probe": probe, "occluded_direction": direction,
               "source_road_sha256": sha(road), "site_sha256": site_hash,
               "construction_sha256": sha(construction_path),
               "fixture_recipe_sha256": sha(dest / "recipe.json"),
               "diagnostic_fixture": True, "physical_acceptance_claimed": False}
    dump(dest / "build-receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", choices=tuple(PROBES), required=True)
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), required=True)
    arguments = parser.parse_args()
    build(arguments.probe, arguments.direction)
