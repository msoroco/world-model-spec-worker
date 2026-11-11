"""Build source-hashed synthetic inputs for the primary CPU compatibility check."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__source_verified_other_right_near_time"
FRAMES = 60


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + "\n"


def lines(rows):
    return "".join(json.dumps(row, allow_nan=False) + "\n" for row in rows)


def box(x, y):
    return [[x-.3,y-.3], [x+.3,y-.3], [x+.3,y+.3], [x-.3,y+.3]]


def build():
    crossing, controller, mapping, trace, evidence = [], [], [], [], []
    for i in range(FRAMES):
        frame, t = 1000+i, i/20
        ex = -8 if i < 20 else min(8, -8 + .8*(i-20))
        oy = -8 if i < 10 else min(8, -8 + .8*(i-10))
        previous = -8 if i <= 10 else min(8, -8 + .8*(i-11))
        seen = previous >= -5.3
        crossing.append({"frame":frame,"time_s":t,"ego_vertices_m":box(ex,0),
                         "ego":{"position_xy_m":[ex,0],"body_vertices_xy_m":box(ex,0)},
                         "other":{"position_xy_m":[0,oy],"body_vertices_xy_m":box(0,oy)}})
        controller.append({"frame":frame,"time_s":t,"other_inside_before_tick":seen,
                           "other_entered_once":seen,"ego_control":{"hold":not seen}})
        mapping.append({"video_frame":i,"carla_frame":frame,"time_s":t})
        trace.append({"frame":frame,"time_s":t,"position":{"x":ex,"y":0,"z":0},
                      "position_m":[ex,0,0],"heading_deg":0,"speed_mps":0 if i<20 else 16})
        evidence.append({"original_frame":frame,"recording_time_s":t,"diagnostic_only":True})
    geometry={"intersection_polygon_xy_m":[[-5,-5],[5,-5],[5,5],[-5,5]],
              "intersection_id":7,"ego_highway_id":1,"other_highway_id":2,
              "device_inventory_source":"synthetic device inventory; no physical claim",
              "device_review":{"official_device_controls_crossing":False,
                               "review_basis":"synthetic CPU fixture"},
              "approach_geometry_source":"synthetic orthogonal approach fixture",
              "ego_approach_heading_deg":0,"other_approach_heading_deg":90,
              "ego_approach_origin_xy_m":[-8,0],"other_approach_origin_xy_m":[0,-8]}
    files={"road_geometry.json":dump(geometry),"crossing_history.jsonl":lines(crossing),
           "controller_history.jsonl":lines(controller),"video_frames.jsonl":lines(mapping),
           "trace.jsonl":lines(trace),"capture/evidence.jsonl":lines(evidence)}
    videos=[{"path":name+".mkv","frames":FRAMES,"width":width,"height":height,
             "fps":20,"color":"black"} for name,width,height in
            (("overview",1920,1080),("approach",1280,720),
             ("reference_corner",1280,720),("driver_reference",1280,720))]
    (HERE/"diagnostic.json").write_text(dump({"files":files,"graphs":[],"videos":videos}))
    origin=HERE/"fixture-origin.json"
    origin.write_text(dump({"format":"worker-synthetic-diagnostic-origin","case_id":CASE,
                            "physical_evidence":False,"purpose":"CPU compatibility only"}))
    def ref(path):
        return {"source":str(path.relative_to(ROOT)),
                "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}
    recipe={"format":"worker-fixture-recipe",
            "sources":[{"path":"fixture-origin.json",**ref(origin)}],
            "generator":ref(HERE/"diagnostic.json")}
    (HERE/"diagnostic-recipe.json").write_text(dump(recipe))
    proposals=HERE/"proposals"
    proposals.mkdir(exist_ok=True)
    (proposals/"cases.json").write_text(dump({"cell_id":"C125714","actor":"motor_vehicle_driver",
        "status":"partial","cases":[{"case_id":CASE,"target_law_id":"NRS-484B-250-2",
        "target_type":"delivery","rationale":"Source-verified right approach and first body entry, synthetic diagnostic only",
        "variable_assignments":{},"recording_description":{"purpose":"synthetic CPU diagnostic"},
        "unresolved_judgment_calls":["approximately same time","statutory right of way"]}],
        "sweep_specs":[],"sweeps_expanded":[]}))
    return recipe


if __name__ == "__main__":
    print(dump(build()))
