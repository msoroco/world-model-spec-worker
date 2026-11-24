"""Build two exact unselected materialization bundles for pinned offline testing."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSIGNMENT = "training__C229977__NRS-484B-450-1a__motor_vehicle_driver"
RUNTIME_SHA = "ade64f2acdaf6d4b653c38f49b71f8c4bd2cf4a985cab7313f160b97b06c3d90"
CAMERAS = [dict(name=n, width=w, height=h) for n,w,h in (
    ("overview",1920,1080),("approach",1280,720),
    ("sidewalk_boundary",1280,720),("driver_reference",1280,720))]
entries = []
for n in (1, 2):
    case_id = ASSIGNMENT + f"__probe_{n}"
    cfg = {"case_id":case_id,"selected_case_id":case_id,"supported_case_ids":[case_id],
           "law_id":"NRS-484B-450-1a","cell_id":"C229977","actor":"motor_vehicle_driver",
           "rate_hz":20,"duration_s":30,"cameras":CAMERAS,"required_atoms":[],
           "source_packets":[],"case":{"case_id":case_id},"status":"unselected_native_draft",
           "recording_description":{"channels":[{"name":"vehicle_body_pose","unit":"structured"},
                    {"name":"vehicle_speed","unit":"m/s"},
                    {"name":"sidewalk_overlap","unit":"m2"}],
              "limitations":["Native road, lateral controller, actual sidewalk use and exceptions unverified"]}}
    files = [
        {"path":"runner.py","content":(HERE/"draft_runner.py").read_text()},
        {"path":"road.xodr","content":(HERE/"draft_road.xodr").read_text()},
        {"path":"config.json","content":json.dumps(cfg,indent=2)+"\n"},
        {"path":"tests/test_draft.py","content":(HERE/"draft_test.py").read_text()},
    ]
    proposal = {"case_id":case_id,"law_id":"NRS-484B-450-1a","cell_id":"C229977",
                "actor":"motor_vehicle_driver","entrypoint":"runner.py","files":files,
                "recording_description":cfg["recording_description"],"status":"draft_not_selected"}
    out = ROOT/f"draft-probe-{n}"
    out.mkdir(exist_ok=True)
    cp = out/"construction.json"
    cp.write_text(json.dumps(proposal,indent=2)+"\n")
    entries.append({"case_id":case_id,"id":"primary","kind":"draft_not_selected",
                    "construction":str(cp.relative_to(ROOT)),
                    "construction_sha256":hashlib.sha256(cp.read_bytes()).hexdigest(),
                    "candidate_risk":{"status":"physical","reason":"Native lateral sidewalk access and physical camera observation unverified"},
                    "candidates":[]})
manifest={"format":"worker-unselected-draft-construction-manifest-v1",
          "assignment_id":ASSIGNMENT,"runtime_manifest_sha256":RUNTIME_SHA,
          "status":"draft_not_selected","cases":entries}
(ROOT/"draft-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
