"""Build source-shaped crest placement, direction and boundary diagnostics.

This changes a textual CPU fixture only. It neither replays accepted sources
nor claims that the planned road, prop or driver sight is physically realized.
"""

import copy
import hashlib
import json
import argparse
from pathlib import Path

from build_crest_opendrive import check_source_geometry, grade
from site_construction import validate_site

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAME = "approach-b"
DEST = HERE / ("branch-proof-" + NAME)
BASE = HERE / "diagnostic-sources-crest-short"
SITE = HERE / "native-map-plan/approach_to_crest__occluded_approach_b.json"
ROAD = HERE / "native-map-plan/crest-road.xodr"
TURN_X = -40
OCCLUDED = "approach_b"
PROBE = "short_of_500ft"
SUFFIX = "short"
CANONICAL = False
CASE_ID = None


def configure(placement, direction, probe="short_of_500ft", canonical=False):
    global NAME, DEST, SITE, TURN_X, OCCLUDED, BASE, PROBE, SUFFIX, CANONICAL, CASE_ID
    if placement not in ("near_summit", "approach_to_crest") or direction not in ("approach_a", "approach_b"):
        raise ValueError("Unknown crest branch")
    if probe not in ("short_of_500ft", "at_500ft", "beyond_500ft"):
        raise ValueError("Unknown crest boundary probe")
    PROBE = probe
    CANONICAL = canonical
    SUFFIX = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}[probe]
    NAME = ("near" if placement == "near_summit" else "approach") + ("-a" if direction == "approach_a" else "-b")
    if probe != "short_of_500ft" or canonical:
        NAME = SUFFIX + "-" + NAME
    if canonical:
        NAME = "canonical-" + NAME
        CASE_ID = HERE.name + "__crest__" + probe + "__" + placement + "__occluded_" + direction
    else:
        CASE_ID = None
    DEST = HERE / ("branch-proof-" + NAME)
    site_name = placement + "__occluded_" + direction + ".json"
    if probe != "short_of_500ft":
        site_name = probe + "__" + site_name
    SITE = HERE / "native-map-plan" / site_name
    BASE = HERE / ("diagnostic-sources-crest-" + SUFFIX)
    TURN_X = 0 if placement == "near_summit" else -40
    OCCLUDED = direction


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def row_lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)


def new_ego_xyz(old):
    x = old[0] + TURN_X
    return [x, old[1] * 1.75 - 1.75, grade(x) + (old[2] - grade(old[0]))]


def new_body(vertices, old_center):
    new_center = new_ego_xyz(old_center)
    return [[new_center[0] + (v[0] - old_center[0]),
             new_center[1] + (v[1] - old_center[1]),
             new_center[2] + (v[2] - old_center[2])] for v in vertices]


def update_observation(obs):
    for participant in obs.get("participants", []):
        old = participant["position_m"]
        participant["body_vertices_m"] = new_body(participant["body_vertices_m"], old)
        participant["position_m"] = new_ego_xyz(old)


def update_visibility(vis, old_center):
    new_center = new_ego_xyz(old_center)
    for sample in vis["ego_body_samples_m"]:
        sample[:] = [new_center[i] + (sample[i] - old_center[i]) for i in range(3)]
    approaches = vis["approaches"]
    if [a["lane_id"] for a in approaches] != [-1, 1]:
        raise ValueError("Expected original A/B lane order")
    # Swapping the lane-specific horizon is a diagnostic source construction.
    # Actual direction-specific rays still require a Native capture.
    if OCCLUDED == "approach_b":
        for row in approaches:
            row["lane_id"] *= -1
        approaches.reverse()


def transform_sources(site, site_hash):
    inputs = {p.relative_to(BASE).as_posix(): p for p in BASE.rglob("*") if p.is_file()}
    target = DEST / "sources"
    transformed = {}
    for name, source in sorted(inputs.items()):
        if name in ("motion_history.jsonl", "turn_history.jsonl", "trace.jsonl",
                    "capture/evidence.jsonl"):
            rows = [json.loads(line) for line in source.read_text().splitlines() if line.strip()]
            if len(rows) != 1100:
                raise ValueError("Incomplete baseline original source: " + name)
            for row in rows:
                if name == "motion_history.jsonl":
                    row["site_source_sha256"] = site_hash
                    ego = row["ego"]
                    ego["location_xyz_m"] = new_ego_xyz(ego["location_xyz_m"])
                    for direction, actor in row["approaches"].items():
                        old = actor["location_xyz_m"]
                        x = old[0] + TURN_X
                        actor["location_xyz_m"] = [x, -1.75 if direction == "approach_a" else 1.75,
                                                   grade(x)]
                elif name == "turn_history.jsonl":
                    vertices = row["body_vertices_m"]
                    old_center = [(min(v[i] for v in vertices) + max(v[i] for v in vertices)) / 2
                                  for i in range(3)]
                    row["body_vertices_m"] = new_body(vertices, old_center)
                elif name == "trace.jsonl":
                    xyz = new_ego_xyz(row["position_m"])
                    row["position_m"] = xyz
                    row["position"] = dict(zip(("x", "y", "z"), xyz))
                else:
                    ego = row["ego"]
                    old = ego["position_m"]
                    ego["body_vertices_m"] = new_body(ego["body_vertices_m"], old)
                    ego["position_m"] = new_ego_xyz(old)
                    update_observation(row["original_observations"])
                    update_visibility(row["visibility"], old)
            content = row_lines(rows)
        elif name == "curve_context.json":
            packet = json.loads(source.read_text())
            packet.update({"site_source_sha256": site_hash,
                           "turn_site_xyz_m": site["turn_site_xyz_m"],
                           "incoming_lanes": site["incoming_lanes"]})
            content = json.dumps(packet, separators=(",", ":")) + "\n"
        elif name == "road.xodr":
            content = ROAD.read_text()
        elif name == "capture/manifest.json":
            content = source.read_text()
        else:
            content = source.read_text()
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Returned source exceeds 2 MiB: " + name)
        transformed[name] = path
    manifest = json.loads(transformed["capture/manifest.json"].read_text())
    if CANONICAL:
        manifest["case_id"] = CASE_ID
    manifest["sources"]["road.xodr"] = sha(transformed["road.xodr"])
    manifest["sources"]["trace.jsonl"] = sha(transformed["trace.jsonl"])
    transformed["capture/manifest.json"].write_text(
        json.dumps(manifest, separators=(",", ":")) + "\n")
    return transformed


def build():
    site = validate_site(json.loads(SITE.read_text()))
    if site["source_status"] != "diagnostic_fixture" or site["occluder"]["target_direction"] != OCCLUDED:
        raise ValueError("Expected unreviewed direction-specific crest packet")
    if site["turn_site_xyz_m"][0] != TURN_X:
        raise ValueError("Unexpected crest placement")
    check_source_geometry(ROAD.read_text(), site)
    DEST.mkdir(exist_ok=True)
    site_path = DEST / ("diagnostic-site-crest-" + SUFFIX + ".json")
    site_path.write_bytes(SITE.read_bytes())
    site_hash = sha(site_path)
    config = json.loads((HERE / ("config-crest-" + SUFFIX + ".json")).read_text())
    if CANONICAL:
        config["selected_case_id"] = CASE_ID
        config["supported_case_ids"] = list(dict.fromkeys(config["supported_case_ids"] + [CASE_ID]))
    config["site_source"] = {"path": site_path.name, "sha256": site_hash}
    config_path = DEST / "config.json"
    dump(config_path, config)
    sources = transform_sources(site, site_hash)
    spec = copy.deepcopy(json.loads((HERE / ("diagnostic-crest-" + SUFFIX + ".json")).read_text()))
    for graph in spec["graphs"]:
        obs = graph["attributes"].get("observed_evidence")
        if obs:
            update_observation(obs)
    spec_path = DEST / "diagnostic.json"
    spec_path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Diagnostic graph specification exceeds 2 MiB")
    items = [{"path": name, "source": str(path.relative_to(ROOT)), "sha256": sha(path)}
             for name, path in sorted(sources.items())]
    items.append({"path": "diagnostic-input.json", "source": str(spec_path.relative_to(ROOT)),
                  "sha256": sha(spec_path)})
    recipe = {"format": "worker-fixture-recipe", "sources": items,
              "generator": {"source": str(spec_path.relative_to(ROOT)), "sha256": sha(spec_path)}}
    dump(DEST / "recipe.json", recipe)
    construction = copy.deepcopy(json.loads((HERE / ("construction-crest-" + SUFFIX + ".json")).read_text()))
    if CANONICAL:
        construction["case_id"] = CASE_ID
    for file in construction["files"]:
        if file["path"] == "config.json":
            file["content"] = config_path.read_text()
            file["source"] = str(config_path.relative_to(ROOT))
        elif file["path"] == site_path.name:
            file["content"] = site_path.read_text()
            file["source"] = str(site_path.relative_to(ROOT))
        elif CANONICAL and file["path"] == "runner.py":
            marker = 'for probe in ("short_of_500ft", "at_500ft", "beyond_500ft")}\n'
            if file["content"].count(marker) != 1:
                raise ValueError("Cannot bind new exact case in runner")
            file["content"] = file["content"].replace(
                marker, marker + "CASES[" + repr(CASE_ID) + "] = ('crest', " + repr(PROBE) + ")\n")
            generated = DEST / "runner.py"
            generated.write_text(file["content"])
            file["source"] = str(generated.relative_to(ROOT))
    construction["branch_engineering"] = {
        "placement": "at sampled crest summit" if TURN_X == 0 else "40 m before authored crest summit",
        "occluded_direction": OCCLUDED,
        "source_status": "diagnostic_fixture", "physical_acceptance_claimed": False}
    construction_path = DEST / "construction.json"
    dump(construction_path, construction)
    manifest = copy.deepcopy(json.loads((HERE / ("diagnostic-crest-" + SUFFIX + "-manifest.json")).read_text()))
    if CANONICAL:
        manifest["cases"][0]["case_id"] = CASE_ID
    manifest["cases"][0]["construction"] = str(construction_path.relative_to(HERE))
    manifest["cases"][0]["construction_sha256"] = sha(construction_path)
    manifest["cases"][0]["fixture_recipe"] = str((DEST / "recipe.json").relative_to(ROOT))
    dump(HERE / ("diagnostic-" + NAME + "-manifest.json"), manifest)
    receipt = {"source_road_sha256": sha(ROAD), "site_sha256": site_hash,
               "construction_sha256": sha(construction_path), "fixture_recipe_sha256": sha(DEST / "recipe.json"),
               "case_id": config["selected_case_id"],
               "probe": PROBE,
               "placement": "near_summit" if TURN_X == 0 else "approach_to_crest",
               "occluded_direction": OCCLUDED, "diagnostic_fixture": True,
               "physical_acceptance_claimed": False}
    dump(DEST / "build-receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--placement", choices=("near_summit", "approach_to_crest"), default="approach_to_crest")
    parser.add_argument("--direction", choices=("approach_a", "approach_b"), default="approach_b")
    parser.add_argument("--probe", choices=("short_of_500ft", "at_500ft", "beyond_500ft"),
                        default="short_of_500ft")
    parser.add_argument("--canonical", action="store_true")
    args = parser.parse_args()
    configure(args.placement, args.direction, args.probe, args.canonical)
    build()
