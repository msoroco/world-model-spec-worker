"""Build exact nine-case source-gated C240647 Native bundles and manifest."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
CAMERAS = (("overview",1920,1080),("approach",1280,720),("reference_corner",1280,720),("driver_reference",1280,720))
FILES = ("runner.py","native_capture.py","native_output_bridge.py","roundabout.py","analysis.py","roundabout_measurements.py","case-plan.json")
BUNDLE_TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import runner
class BundleTests(unittest.TestCase):
    def test_exact_selected_case(self):
        self.assertEqual(runner.check()["case_id"],json.loads((runner.HERE/"config.json").read_text())["selected_case_id"])
    def test_reviewed_original_source_required(self):
        with patch("sys.argv",["runner.py","--host","localhost","--port","2000","--output-dir","attempt"]):
            with patch.dict("os.environ",{},clear=True):
                with self.assertRaisesRegex(ValueError,"source-hashed reviewed roundabout"):
                    runner.main()
if __name__ == "__main__":
    unittest.main()
'''

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    plan_bytes=(HERE/"case-plan.json").read_bytes()
    plan=json.loads(plan_bytes)
    cases=plan["cases"]
    ids=[row["case_id"] for row in cases]
    if len(ids)!=9 or len(set(ids))!=9 or any(not cid.startswith(AID+"__") for cid in ids):
        raise ValueError("nine exact roundabout controls required")
    source={name:(HERE/name).read_text() for name in FILES}
    (HERE/"tests/test_bundle.py").write_text(BUNDLE_TEST)
    channels=[{"name":name,"unit":"structured","sampling_rate_hz":20,
               "method":"source-sealed original Native readback","time_window":"all 900 ticks",
               "reference_frame":"original CARLA map/world","uncertainty":"physical capture pending"}
              for name in ("original_roundabout_topology","independent_operator_intent",
                           "original_ring_lane_history","actual_exit_connector","original_four_camera_pixels")]
    description={"channels":channels,"context_inputs":[{"name":"reviewed_roundabout_map","unit":"source",
                    "method":"source-hashed original OpenDRIVE and lane/connector survey"}],
                 "limitations":["Intent is independently sourced; actual lane and exit require original actor readback.",
                                "Right-turn and right-lane legal judgments remain unresolved."]}
    entries=[]
    for row in cases:
        case=row["case_id"]
        name=case.removeprefix(AID+"__")
        for candidate,throttle in (("primary",.35),("fallback1",.25)):
            config={"assignment_id":AID,"law_id":"LVMC-11-43-010-C2","cell_id":"C240647",
                    "actor":"motor_vehicle_driver","selected_case_id":case,"supported_case_ids":ids,
                    "plan_sha256":hashlib.sha256(plan_bytes).hexdigest(),"rate_hz":20,"duration_s":45,
                    "required_atoms":[],"source_packets":[],"route_throttle":throttle,
                    "cameras":[{"name":view,"width":width,"height":height,"fov_deg":80,
                                "pose_strategy":"original approach, circulating right/left lanes, connector and actor body"}
                               for view,width,height in CAMERAS],"case":dict(row,recording_description=description)}
            content=dict(source)
            content["config.json"]=json.dumps(config,sort_keys=True,indent=2)+"\n"
            content["tests/test_bundle.py"]=BUNDLE_TEST
            construction={"law_id":"LVMC-11-43-010-C2","cell_id":"C240647","actor":"motor_vehicle_driver",
                          "case_id":case,"entrypoint":"runner.py","recording_description":description,
                          "measurement_plan":{"case_id":case,"source_packets":["map","history"],
                                              "procedure":"analysis.py","legal_judgment":"unresolved"},
                          "static_checks":["reviewed jurisdiction and source-hashed lane/connector graph",
                                           "independent intent before movement","900 original 20 Hz actor and camera frames"],
                          "termination_rules":["900 original Native ticks","source-observed exit or continued circulation"],
                          "mechanisms":["reviewed OpenDRIVE roundabout survey","source-hashed Native operator",
                                        "exact right/left lane route tracking","four synchronized RGB cameras"],
                          "files":[{"path":path,"content":data} for path,data in content.items()]}
            relative=Path("cases")/name/("construction.json" if candidate=="primary" else "fallback1/construction.json")
            path=HERE/relative
            write(path,construction)
            if name==cases[0]["case_id"].removeprefix(AID+"__") and candidate=="primary":
                write(HERE/"config.json",config)
                write(HERE/"construction.json",construction)
            if candidate=="primary":
                entries.append({"case_id":case,"kind":"delivery","construction":str(relative),
                                "construction_sha256":sha(path),"candidate_risk":{"status":"physical",
                                "reason":"Mapped circular lane change or connector transition may overshoot under reviewed vehicle dynamics."},
                                "measurement_procedure":{"entrypoint":"analysis.py",
                                                         "method":"saved original lane/intent/connector measurement"},
                                "native_handoff":{"python_env_var":"CARLA_PYTHON","host_env_var":"CARLA_HOST",
                                                  "port_env_var":"CARLA_PORT"},"candidates":[]})
            else:
                entries[-1]["candidates"].append({"id":"fallback1","construction":str(relative),
                        "construction_sha256":sha(path),"changed_knobs":["route throttle 0.25 instead of 0.35"],
                        "trigger":{"source":"original actor position and mapped waypoint readback",
                                   "metric":"circular lane or connected exit overshoot",
                                   "failure_condition":"primary steering fails to reach requested mapped connector"}})
    write(HERE/"execution-manifest.json",{"format":"worker-execution-manifest","assignment_id":AID,
          "runtime_manifest_sha256":sha(REPO/"runtime/SOURCE-MANIFEST.json"),"cases":entries})
    return len(entries)

if __name__ == "__main__":
    print(build())
