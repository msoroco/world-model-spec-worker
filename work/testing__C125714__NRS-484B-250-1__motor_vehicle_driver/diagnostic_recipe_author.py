"""Author an exact-case textual fixture; all content is synthetic CPU data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VARIANTS = (("precedence", 4, 2), ("advance", 4, 2), ("other_later", 2, 4),
            ("opposite_straight", 4, 2), ("opposite_intends_left", 4, 2),
            ("opposite_makes_left", 4, 3), ("wide_same_crossing", 4, 2))


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"


def body(x, y):
    return [[x-.2, y-.2], [x+.2, y-.2], [x+.2, y+.2], [x-.2, y+.2]]


def build_variant(suffix, ego_entry, other_entry):
    folder = ROOT if suffix == "precedence" else ROOT / "cases" / suffix
    scene = json.loads((folder / "scene.json").read_text())
    crossing = scene["crossing"]
    context = {
        "diagnostic_only": True, "ego_actor_id": 11, "other_actor_id": 22,
        "crossing": crossing,
        "law_context": {
            "map_source": crossing["map_source_sha256"],
            "ego_highway": scene["ego_highway"], "other_highway": scene["other_highway"],
            "public_access_source": "synthetic CPU fixture only",
            "device_inventory_source": "synthetic CPU fixture only",
            "driver_scope_source": "synthetic CPU fixture only",
            "public_access": True, "human_driver": True, "devices": [],
            "approach_relation": scene["approach_relation"],
            "left_turn_intent": scene["left_turn_intent"],
            "left_turn_realized": scene["left_turn_realized"]}}
    files = {"intersection-context.json": encoded(context)}
    for name, actor, entry, cleared in (("ego", 11, ego_entry, 6),
                                        ("other", 22, other_entry, 6)):
        rows = []
        for frame in range(9):
            coordinate = -10 if frame < entry else (0 if frame < cleared else 10)
            if suffix == "wide_same_crossing" and name == "ego":
                x, y = -coordinate, 5.75
            elif suffix == "wide_same_crossing":
                x, y = 0, (-10 if frame < entry else (5.75 if frame < cleared else 10))
            elif name == "ego":
                x, y = coordinate, -5.75
            elif suffix == "opposite_makes_left":
                x, y = ((10, 5.75), (8, 5.75), (4, 5.75),
                        (-.066, 4.066), (-1.75, 0), (-1.75, -5),
                        (-1.75, -10), (-1.75, -13), (-1.75, -15))[frame]
            elif scene["approach_relation"] == "opposite":
                x, y = -coordinate, 5.75
            else:
                x, y = 0, coordinate
            rows.append(encoded({"frame": frame, "time_s": frame/20,
                                 "actor_id": actor, "body_vertices_xy_m": body(x, y)}))
        files[f"{name}-body-history.jsonl"] = "".join(rows)
    acquired = {name: {"kind": "original_native",
                       "sha256": hashlib.sha256(files[name].encode()).hexdigest()}
                for name in ("intersection-context.json", "ego-body-history.jsonl",
                             "other-body-history.jsonl")}
    files["acquisition.json"] = encoded(acquired)
    files["acquisition-provenance.json"] = encoded(
        {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    files["trace.jsonl"] = "".join(encoded({"frame": frame, "time_s": frame/20,
                                             "position_m": ([10 if frame < ego_entry else (0 if frame < 6 else -10), 5.75]
                                                            if suffix == "wide_same_crossing" else
                                                            [-10 if frame < ego_entry else (0 if frame < 6 else 10), -5.75])})
                                     for frame in range(9))
    files["video_frames.jsonl"] = "".join(encoded(
        {"video_frame": frame, "carla_frame": frame, "native_frame": frame,
         "time_s": frame/20}) for frame in range(9))
    videos = [{"path": name+".mkv", "frames": 9, "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, width, height in (("overview", 1920, 1080),
                                          ("approach", 1280, 720),
                                          ("reference_corner", 1280, 720),
                                          ("driver_reference", 1280, 720))]
    spec = {"files": files, "graphs": [], "videos": videos}
    path = folder / "diagnostic.json"
    path.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    source = str(path.relative_to(ROOT.parent.parent))
    map_source = ROOT / "candidate-map.xodr"
    recipe = {"format": "worker-fixture-recipe", "sources": [{
                  "path": "road.xodr", "source": str(map_source.relative_to(ROOT.parent.parent)),
                  "sha256": hashlib.sha256(map_source.read_bytes()).hexdigest()}],
              "generator": {"source": source, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    (folder / "diagnostic-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")


def build():
    for suffix, ego_entry, other_entry in VARIANTS:
        build_variant(suffix, ego_entry, other_entry)


if __name__ == "__main__":
    build()
