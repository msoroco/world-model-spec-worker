"""Check the exact scope/camera joins before Native capture is implemented."""

import json
from pathlib import Path

from stop_yield_scene import CASES, request, validate


def check(plan, config):
    aid = "training__C111325__NRS-484B-257-1__motor_vehicle_driver"
    if (config.get("assignment_id"), config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            aid, "NRS-484B-257-1", "C111325", "motor_vehicle_driver"):
        raise ValueError("Exact law/cell/actor capture identity differs")
    planned = {case["case_id"] for case in plan["cases"]}
    if set(config.get("supported_case_ids", [])) != planned or len(planned) != len(CASES):
        raise ValueError("Capture design omits an exact statutory case")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30 or config.get("frames") != 600:
        raise ValueError("Capture design lacks full source history")
    expected = [("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
    cameras = config.get("cameras", [])
    if [(c.get("name"), c.get("width"), c.get("height")) for c in cameras] != expected or any(
            not c.get("pose_strategy") or not c.get("fov_deg") for c in cameras):
        raise ValueError("Capture design differs from pinned four-view profile")
    if config.get("recording_description") != plan.get("recording_description"):
        raise ValueError("Capture observation description differs from plan")
    for case in plan["cases"]:
        if case.get("recording_description") != config["recording_description"]:
            raise ValueError("Exact case changed recording observations")
        slug = case["case_id"].removeprefix(aid + "__")
        scene = request(slug)
        validate(scene)
        if [(camera["name"], camera["width"], camera["height"]) for camera in scene["cameras"]] != expected:
            raise ValueError("Scene camera request differs from capture design")
    if config.get("physical_acceptance_claimed") is not False or config.get("legal_verdict") is not None:
        raise ValueError("Capture design claimed physical or legal completion")
    return {"case_count": len(planned), "camera_count": len(cameras),
            "physical_acceptance_claimed": False}


def rejects(plan, config, phrase):
    try:
        check(plan, config)
    except ValueError as error:
        if phrase not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid capture design passed")


def main():
    folder = Path(__file__).resolve().parent
    plan = json.loads((folder / "case-plan.json").read_text())
    config = json.loads((folder / "config.json").read_text())
    assert check(plan, config)["case_count"] == 12
    changed = json.loads(json.dumps(config))
    changed["supported_case_ids"].pop()
    rejects(plan, changed, "omits")
    changed = json.loads(json.dumps(config))
    changed["cameras"][2]["width"] = 640
    rejects(plan, changed, "four-view")
    changed = json.loads(json.dumps(config))
    changed["physical_acceptance_claimed"] = True
    rejects(plan, changed, "physical or legal")
    print("12-case capture design and three identity/camera/claim negatives passed; no Native capture")


if __name__ == "__main__":
    main()
