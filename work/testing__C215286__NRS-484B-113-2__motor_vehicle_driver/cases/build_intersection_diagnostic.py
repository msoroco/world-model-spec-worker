"""Build one full-duration synthetic reverse-alternative compatibility fixture.

The fixture exercises source joins and decoder paths. It does not assert
Native acquisition or physical legal acceptance.
"""

import copy
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
REPO = ASSIGNMENT.parents[1]
INDEX = int(sys.argv[1]) if len(sys.argv) > 1 else 0
if INDEX not in range(4):
    raise ValueError("Select one of four staged alternatives")
FIXTURE = HERE / "fixtures" / str(INDEX)


def compact(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def lines(rows):
    return "".join(compact(row) + "\n" for row in rows)


def digest(content):
    return hashlib.sha256(content.encode()).hexdigest()


def main():
    source = json.loads((ASSIGNMENT / "diagnostic.json").read_text())
    manifest = json.loads((HERE / "alternative-offline-manifest.json").read_text())
    case = manifest["cases"][INDEX]
    bundle = json.loads((HERE / case["construction"]).read_text())
    config = json.loads(next(item["content"] for item in bundle["files"]
                             if item["path"] == "config.json"))
    site_source = config["site_packet"]
    site = json.loads((FIXTURE / site_source).read_text())
    route = site["route_xy_m"]
    original = source["files"]
    first = {name: json.loads(original[name].splitlines()[0]) for name in
             ("reverse_history.jsonl", "video_frames.jsonl", "trace.jsonl",
              "capture/evidence.jsonl", "capture/native/frames.jsonl")}
    files = {"road.xodr": original["road.xodr"],
             "capture/recorder_info.txt": original["capture/recorder_info.txt"]}
    context = {"alternative": site["alternative"],
               "expected_entry": site["expected_entry"],
               "native_map_id": site["native_map_id"],
               "road_id": site["road_id"],
               "site_packet_source": {"path": site_source,
                                      "sha256": hashlib.sha256((FIXTURE / site_source).read_bytes()).hexdigest()},
               "geometry_source": site["geometry_source"],
               "camera_source": site["camera_source"],
               "road_topology_source": site.get("road_topology_source"),
               "intersection_polygon_xy_m": site["region_polygon_xy_m"]
               if site["alternative"] == "intersection" else None,
               "street_corner_region_xy_m": site["region_polygon_xy_m"]
               if site["alternative"] == "street_corner" else None}
    files["reverse_site_context.json"] = compact(context) + "\n"
    collected = {name: [] for name in first}
    graphs = []
    for i in range(900):
        frame, time = 100 + i, round((i + 1) / 20, 8)
        position = min(i / 5, len(route) - 1)
        start = int(position)
        fraction = position - start
        nxt = min(start + 1, len(route) - 1)
        x = round(route[start][0] * (1 - fraction) + route[nxt][0] * fraction, 5)
        y = round(route[start][1] * (1 - fraction) + route[nxt][1] * fraction, 5)
        moving = i < 5 * (len(route) - 1)
        velocity = [-4, 0, 0] if moving else [0, 0, 0]
        speed = 4 if moving else 0
        heading = (round(min(90, max(0, (position - 8) * 90 / (len(route) - 9))), 3)
                   if site["alternative"] == "street_corner" and site["expected_entry"]
                   else 0)
        body2 = [[x - 1, y - 1], [x + 1, y - 1],
                 [x + 1, y + 1], [x - 1, y + 1]]
        body3 = [[point[0], point[1], 0] for point in body2]
        history = copy.deepcopy(first["reverse_history.jsonl"])
        history.update(frame=frame, time_s=time, native_reverse=True,
                       ego_body_vertices_xy_m=body2, body_vertices_m=body2,
                       heading_deg=heading, velocity_mps=velocity[:2])
        collected["reverse_history.jsonl"].append(history)
        mapping = {"video_frame": i, "carla_frame": frame,
                   "native_frame": frame, "time_s": time}
        collected["video_frames.jsonl"].append(mapping)
        trace = copy.deepcopy(first["trace.jsonl"])
        trace.update(frame=frame, time_s=time, position={"x": x, "y": y, "z": .3},
                     position_m=[x, y, .3], heading_deg=heading, speed_mps=speed,
                     velocity_mps=velocity, speed_mph=round(speed * 2.2369362921, 6))
        collected["trace.jsonl"].append(trace)
        evidence = copy.deepcopy(first["capture/evidence.jsonl"])
        evidence.update(original_frame=frame, replay_frame=frame,
                        recording_time_s=time, replay_simulation_time_s=time)
        evidence["ego"].update(position_m=[x, y, .3], heading_deg=heading,
                               speed_mps=speed, body_vertices_m=body3)
        if INDEX == 2:
            for optional in ("world", "timing", "visibility", "supporting_only"):
                evidence.pop(optional, None)
        observation = evidence["original_observations"]
        observation.update(frame=frame, time_s=time)
        observation["participants"][0].update(
            blueprint="vehicle.tesla.model3", position_m=[x, y, .3],
            heading_deg=heading, speed_mps=speed, velocity_mps=velocity,
            body_vertices_m=body3)
        collected["capture/evidence.jsonl"].append(evidence)
        graph_name = f"{frame:08d}.adapter.json"
        native = copy.deepcopy(first["capture/native/frames.jsonl"])
        native.update(frame=frame, simulation_time=time,
                      base="graphs/base/" + graph_name,
                      abstract="graphs/abstract/" + graph_name,
                      adapter_graph="graphs/base/" + graph_name)
        collected["capture/native/frames.jsonl"].append(native)
        for kind in ("base", "abstract"):
            attributes = {"frame": frame, "simulation_time_s": time,
                          "units": {"position": "m"}}
            if kind == "base":
                attributes["observed_evidence"] = observation
            graphs.append({"path": f"capture/native/graphs/{kind}/{graph_name}",
                           "attributes": attributes,
                           "nodes": [], "edges": []})
    for name, rows in collected.items():
        files[name] = lines(rows)
    native_manifest = json.loads(original["capture/manifest.json"])
    native_manifest.update(case_id=case["case_id"], frames=900)
    native_manifest["required_observations"] = ["kin.position", "kin.heading",
                                                 "kin.velocity",
                                                 "st.intersection" if site["alternative"] == "intersection"
                                                 else "st.street_corner", "rel.occupies"]
    native_manifest["sources"]["trace.jsonl"] = digest(files["trace.jsonl"])
    files["capture/manifest.json"] = compact(native_manifest) + "\n"
    spec = {"files": files, "graphs": graphs,
            "videos": [dict(video, frames=900) for video in source["videos"]]}
    encoded = compact(spec) + "\n"
    destination = FIXTURE / "full-diagnostic.json"
    if len(encoded.encode()) > 2_097_152:
        print("Full diagnostic too large:", len(encoded.encode()))
        return
    destination.write_text(encoded)
    recipe = json.loads((FIXTURE / "site-source-recipe.json").read_text())
    recipe["generator"] = {"source": destination.relative_to(REPO).as_posix(),
                           "sha256": digest(encoded)}
    (FIXTURE / "full-diagnostic-recipe.json").write_text(
        json.dumps(recipe, indent=2) + "\n")
    print("full diagnostic", len(encoded.encode()), "bytes;", len(graphs), "graphs")


if __name__ == "__main__":
    main()
