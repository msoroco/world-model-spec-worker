"""Materialize source-exact construction drafts for all seven selected cases.

These bind CPU-authored files. They carry no offline or compatibility receipt.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SHARED=("runner.py","case_builder.py","uturn_control.py","native_driver.py",
        "divider_construction.py","native_capture.py","uturn_audit.py",
        "analysis.py","delivery_audit.py","comparison_audit.py")


def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n")


def file_entry(target,source):
    source=Path(source).resolve()
    if not source.is_relative_to(HERE):
        raise ValueError("construction source left assignment work directory")
    return {"path":target,"source":str(source.relative_to(REPO)),
            "content":source.read_text()}


def build():
    plan=json.loads((HERE/"case-plan.json").read_text())
    common_contract=json.loads((HERE/"measurement-contract.json").read_text())
    built=[]
    for case in plan["cases"]:
        ident=case["case_id"]
        suffix=ident.rsplit("__",1)[-1]
        location=HERE/"cases"/suffix
        location.mkdir(parents=True,exist_ok=True)
        original=HERE if suffix=="opening_single" else location
        scene_path=original/"scene.json"
        config_path=original/"config.json"
        scene=json.loads(scene_path.read_text())
        config=json.loads(config_path.read_text())
        if scene["case_id"]!=ident or config["selected_case_id"]!=ident:
            raise ValueError("exact case construction identity differs")
        map_path=original/scene["map_source"]
        review_path=original/scene["reviewed_context_source"]
        authority_path=original/scene["authority_review_source"]
        reviewed=json.loads(review_path.read_text())
        reviewed["map_source"]="road.xodr"
        reviewed_text=json.dumps(reviewed,indent=2,sort_keys=True)+"\n"
        bundle_scene=dict(scene)
        bundle_scene.update(map_source="road.xodr",
                            reviewed_context_source="reviewed-median-context.json",
                            reviewed_context_sha256=hashlib.sha256(reviewed_text.encode()).hexdigest(),
                            authority_review_source="authority-review-source.json")
        offline_test='''import hashlib, json, unittest\nfrom pathlib import Path\nfrom runner import check_scene\n\nclass OfflineCase(unittest.TestCase):\n    def test_source_bound_scene(self):\n        scene=json.loads(Path("scene.json").read_text())\n        check_scene(scene)\n        self.assertEqual(hashlib.sha256(Path("road.xodr").read_bytes()).hexdigest(),scene["context"]["map_source_sha256"])\n        self.assertEqual(hashlib.sha256(Path("reviewed-median-context.json").read_bytes()).hexdigest(),scene["reviewed_context_sha256"])\n        self.assertEqual(hashlib.sha256(Path("authority-review-source.json").read_bytes()).hexdigest(),scene["context"]["authority_review_source_sha256"])\n'''
        sources=[file_entry(name,HERE/name) for name in SHARED]
        sources.extend(({"path":"scene.json","content":json.dumps(bundle_scene,indent=2,sort_keys=True)+"\n"},
                        file_entry("config.json",config_path),
                        file_entry("road.xodr",map_path),
                        {"path":"reviewed-median-context.json","content":reviewed_text},
                        file_entry("authority-review-source.json",authority_path),
                        {"path":"tests/test_offline.py","content":offline_test}))
        target=config["case"]["physical_target"]
        construction={"law_id":"NRS-484B-227-1","cell_id":"C80909",
            "actor":"motor_vehicle_driver","case_id":ident,
            "entrypoint":"runner.py","files":sources,
            "recording_description":config["case"]["recording_description"],
            "mechanisms":["source-hashed OpenDRIVE and reviewed median geometry",
                          "actual Native divider actors with footprint audit",
                          "source-bound original body, heading and velocity histories",
                          "physical target: "+target],
            "measurement_plan":{"median_uturn_measurement":
                "Original four-corner body and heading measured against reviewed opening, divider and right-roadway regions; public-authority/legal judgment unresolved."},
            "static_checks":["exact case, map, context, authority source and config hashes",
                             "authored route and planned full-body clearance",
                             "20 Hz four-camera Native configuration"],
            "termination_rules":["stop after authored route target or duration_s",
                                 "retain all original Native sources and restoration proof"]}
        write(location/"construction.json",construction)
        write(location/"measurement-contract.json",common_contract)
        built.append({"case_id":ident,
                      "construction":str((location/"construction.json").relative_to(HERE)),
                      "measurement_contract":str((location/"measurement-contract.json").relative_to(HERE))})
    old=HERE/"construction.json"
    if old.exists():old.unlink()
    return built


if __name__=="__main__":
    print(json.dumps({"construction_drafts":build(),"delivery_ready_claimed":False},sort_keys=True))
