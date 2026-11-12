"""Shared config description of the four actual candidate camera poses."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from cameras import camera_plan


def cameras():
    plans = {name: camera_plan(name) for name in
             ("primary", "fallback1", "fallback2", "fallback3")}
    baseline = plans["primary"]
    output = []
    for index, camera in enumerate(baseline):
        same = [plans[name][index] for name in plans]
        if any((item["name"], item["width"], item["height"], item["attachment"],
                item["xyz_m"]) !=
               (camera["name"], camera["width"], camera["height"], camera["attachment"],
                camera["xyz_m"]) for item in same):
            raise ValueError("Candidate cameras changed shared pose or dimensions")
        output.append({"name": camera["name"], "width": camera["width"],
                       "height": camera["height"], "fov_deg": camera["fov_deg"],
                       "fov_by_candidate": {name: plans[name][index]["fov_deg"]
                                            for name in plans},
                       "pose_strategy": "Native " + camera["attachment"] +
                                        " attachment at authored xyz_m; verify pixels after capture",
                       "attachment": camera["attachment"],
                       "xyz_m": camera["xyz_m"], "purpose": camera["purpose"]})
    return output
