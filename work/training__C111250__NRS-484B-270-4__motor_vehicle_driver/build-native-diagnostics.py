"""Build transparent synthetic source-shape fixtures for the new Native path."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from route_v2 import route_x


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))


def main():
    import shutil
    for suffix, old, route in (("controlled_1", "primary", "outside_cycle_lane"),
                               ("controlled_2", "contrast", "within_cycle_lane")):
        source = HERE / ("current-v2-" + old + "-sources")
        target = HERE / ("native-diagnostic-" + suffix + "-sources")
        if not target.exists():
            shutil.copytree(source, target)
        facility = json.loads((target / "facility-context.json").read_text())
        facility.update(native_map_sha256="synthetic_map_shape_only",
                        native_facility_readback={"mock_survey": True},
                        native_lane_survey=[{"lane_id": -1 if i % 2 == 0 else -2,
                                             "source_kind": "synthetic_cpu_diagnostic"}
                                            for i in range(6)])
        write(target / "facility-context.json", facility)
        write(target / "subsection3-context.json", {
            "source_kind": "synthetic_cpu_diagnostic",
            "exception_clause_requested": "NRS 484B.270(3)(c), to avoid conflict with other traffic",
            "conflict_actor_id": 99,
            "subsection3_conflict_context": {"mock_conflict_actor": True},
            "conflict_actor_body_xy_m": [[.8,-4.1],[2.7,-4.1],[2.7,-1.9],[.8,-1.9]],
            "exception_legally_resolved": False,
            "yield_to_facility_users_observed": False,
            "mock_source_shape_only": True})
        bodies = read_rows(target / "body-history.jsonl")
        trace = read_rows(target / "trace.jsonl")
        evidence = read_rows(target / "capture/evidence.jsonl")
        spec = json.loads((HERE / ("current-v2-" + old + "-fixture-spec.json")).read_text())
        for index in range(600):
            y = trace[index]["position"]["y"]
            x = route_x(route, y)
            body = [[x + dx, y + dy] for dx, dy in
                    ((-.9,-2.2),(.9,-2.2),(.9,2.2),(-.9,2.2))]
            vertices = [[px,py,z] for px,py in body for z in (0.0,1.5)]
            bodies[index]["body_xy_m"] = body
            trace[index]["position"]["x"] = x
            trace[index]["position_m"][0] = x
            trace[index]["velocity_mps"] = [0.0, 3.4, 0.0]
            evidence[index]["ego"]["body_vertices_m"] = vertices
            evidence[index]["ego"]["position_m"][0] = x
            evidence[index]["world"]["road_projection"]["lane_id"] = -2 if x >= 3.5 else -1
            graph = spec["graphs"][index]
            graph["nodes"][0]["attributes"]["vertex"][0] = x
            graph["nodes"][0]["attributes"]["threedbbox"] = vertices
        write_rows(target / "body-history.jsonl", bodies)
        write_rows(target / "trace.jsonl", trace)
        write_rows(target / "capture/evidence.jsonl", evidence)
        manifest = json.loads((target / "capture/manifest.json").read_text())
        manifest["synthetic_diagnostic"] = True
        manifest["sources"]["trace.jsonl"] = sha(target / "trace.jsonl")
        write(target / "capture/manifest.json", manifest)
        spec_path = HERE / ("native-diagnostic-" + suffix + "-spec.json")
        write(spec_path, spec)
        recipe = {"format": "worker-fixture-recipe", "sources": [
            {"path": str(path.relative_to(target)), "source": str(path.relative_to(REPO)),
             "sha256": sha(path)} for path in sorted(target.rglob("*")) if path.is_file()],
            "generator": {"source": str(spec_path.relative_to(REPO)),
                          "sha256": sha(spec_path)}}
        recipe_path = HERE / ("native-diagnostic-" + suffix + "-recipe.json")
        write(recipe_path, recipe)
        print(json.dumps({"case": suffix, "recipe_sha256": sha(recipe_path),
                          "spec_sha256": sha(spec_path)}))


if __name__ == "__main__":
    main()
