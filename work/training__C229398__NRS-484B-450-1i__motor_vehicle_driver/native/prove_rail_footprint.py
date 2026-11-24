"""Deterministic diagnostic proof for the nearest-rail source meter."""
import copy
import hashlib
import json
from pathlib import Path

from rail_footprint_meter import measure


def packet(offset_m, reason="voluntary"):
    rails=[{"rail_id":"west_rail","source_kind":"map_survey","source_ref":"map:west-rail-polyline",
            "polyline_xy_m":[[0,-20],[0,20]]},
           {"rail_id":"east_rail","source_kind":"map_survey","source_ref":"map:east-rail-polyline",
            "polyline_xy_m":[[1.5,-20],[1.5,20]]}]
    frames=[]
    for i in range(600):
        # At rest for 20 seconds; the first 10 seconds expose the approach.
        x=offset_m if i>=200 else offset_m+(200-i)*0.01
        frames.append({"frame":i,"sim_time_s":i/20,"vehicle_footprint_xy_m":
                       [[x,-1],[x+4,-1],[x+4,1],[x,1]],
                       "pose_source_ref":"native:ego-transform","extent_source_ref":"native:ego-bbox",
                       "speed_source_ref":"native:ego-velocity","speed_mps":0 if i>=200 else 0.2,
                       "halt_reason":reason if i>=200 else "unknown",
                       "halt_reason_source_ref":"native:control-and-actor-trace" if i>=200 else None})
    return {"format":"rail-footprint-native-source-v1","rails":rails,"frames":frames}


def rejected(value, phrase):
    try:
        measure(value)
    except ValueError as error:
        assert phrase in str(error), str(error)
        return str(error)
    raise AssertionError("negative source unexpectedly accepted")


def main():
    inside=measure(packet(14.0))
    outside=measure(packet(18.0))
    forced=measure(packet(14.0,"traffic_conflict"))
    assert len(inside["frames"])==len(outside["frames"])==600
    assert all(x["nearest_rail_id"]=="east_rail" for x in inside["frames"])
    assert inside["frames"][300]["footprint_to_nearest_rail_m"]==12.5
    assert outside["frames"][300]["footprint_to_nearest_rail_m"]==16.5
    assert inside["frames"][300]["inside_50ft_band"]
    assert not outside["frames"][300]["inside_50ft_band"]
    assert forced["frames"][300]["halt_reason"]=="traffic_conflict"
    assert sum(x["at_rest"] for x in inside["frames"])==400
    negatives={}
    bad=packet(14.0);bad["rails"]=bad["rails"][:1]
    negatives["missing_nearest_rail"]=rejected(bad,"both physical rails")
    bad=packet(14.0);bad["rails"][1]["source_ref"]=""
    negatives["unsourced_rail"]=rejected(bad,"rail survey source")
    bad=packet(14.0);bad["frames"][300].pop("extent_source_ref")
    negatives["unsourced_extent"]=rejected(bad,"Native pose, extent")
    bad=packet(14.0);bad["frames"][300]["frame"]=301
    negatives["bad_frame_map"]=rejected(bad,"frame map")
    bad=packet(14.0);bad["frames"][300]["halt_reason_source_ref"]=""
    negatives["unsourced_exception"]=rejected(bad,"halt reason source")
    bad=packet(14.0);bad["frames"][300].pop("vehicle_footprint_xy_m")
    negatives["missing_footprint"]=rejected(bad,"four vehicle footprint")
    root=Path(__file__).resolve().parents[1]
    construction=json.loads((root/"native"/"unselected-rail-construction.json").read_text())
    assert construction["duration_frames"]==600 and construction["fps"]==20
    assert construction["condition_a"]["target_footprint_gap_m"]==12.5
    assert construction["condition_b"]["target_footprint_gap_m"]==16.5
    assert construction["rail_source_kind"]=="map_survey_or_native_survey"
    output={"format":"rail-footprint-cpu-proof-v1","passed":True,"simulation_started":False,
            "source_label":"synthetic_native_sample","frames_per_case":600,
            "inside_rest_frames":sum(x["at_rest"] and x["inside_50ft_band"] for x in inside["frames"]),
            "outside_rest_frames":sum(x["at_rest"] and not x["inside_50ft_band"] for x in outside["frames"]),
            "forced_halt_rest_frames":sum(x["at_rest"] and x["inside_50ft_band"] and x["halt_reason"]=="traffic_conflict" for x in forced["frames"]),
            "negative_rejections":negatives,
            "meter_sha256":hashlib.sha256((root/"native"/"rail_footprint_meter.py").read_bytes()).hexdigest(),
            "construction_sha256":hashlib.sha256((root/"native"/"unselected-rail-construction.json").read_bytes()).hexdigest()}
    print(json.dumps(output,indent=2))


if __name__=="__main__":
    main()
