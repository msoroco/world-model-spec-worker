"""Right-turn geometry variants for the statute's stopping-reference hierarchy."""
import xml.etree.ElementTree as ET

from geometry import (INTERSECTION_NEAR_Y_M, STOP_LINE_Y_M, check as base_check,
                      open_drive as base_open_drive)

ABSENT = ("absent_reference", "absent_reference_contrast")


def open_drive_for(case_suffix):
    if case_suffix not in ("reference", "contrast", *ABSENT):
        raise ValueError("Unknown right-turn geometry variant")
    if case_suffix not in ABSENT:
        return base_open_drive()
    root = ET.fromstring(base_open_drive())
    approach = next(road for road in root.findall("road") if road.attrib["id"] == "1")
    objects = approach.find("objects")
    for item in list(objects):
        if item.attrib.get("name") in ("nearest-side-crosswalk", "stop-line"):
            objects.remove(item)
    root.find("header").set("name", "C110919-red-right-turn-absent-reference")
    return ET.tostring(root, encoding="unicode")


def check_for(case_suffix):
    if case_suffix not in ("reference", "contrast", *ABSENT):
        raise ValueError("Unknown right-turn geometry variant")
    check = base_check()
    root = ET.fromstring(open_drive_for(case_suffix))
    approach = next(road for road in root.findall("road") if road.attrib["id"] == "1")
    names = {item.attrib.get("name") for item in approach.findall("objects/object")}
    absent = case_suffix in ABSENT
    if absent:
        if names & {"nearest-side-crosswalk", "stop-line"}:
            raise ValueError("Absent-reference approach still contains a stop object")
        if root.find(".//object[@name='destination-pedestrian-crosswalk']") is None:
            raise ValueError("Destination pedestrian conflict missing")
    elif not {"nearest-side-crosswalk", "stop-line"} <= names:
        raise ValueError("Marked stopping reference missing")
    if len(root.findall(".//signal[@id='601']")) != 1:
        raise ValueError("Governing signal proposal changed")
    return {**check, "case_suffix": case_suffix,
            "stopping_reference_kind": "intersection_boundary" if absent else "marked_stop_line",
            "stopping_reference_y_m": INTERSECTION_NEAR_Y_M if absent else STOP_LINE_Y_M,
            "nearest_crosswalk_or_stop_marking_present": not absent,
            "absence_proof_kind": "authored_OpenDRIVE_object_inventory_only",
            "native_absence_observed": False}
