"""Diagnostic-only four-camera source audit, with a missing-media negative."""
from __future__ import annotations

import argparse
import io
import json
import shutil
from pathlib import Path

from PIL import Image

from delivery_audit import audit
from native_acquisition import VIEWS, capture

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[1] / ".runtime-work/c213645-owner"
PLAN = json.loads((HERE / "case-plan.json").read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    selected = [row for row in PLAN["cases"] if row["case_id"] == args.case]
    if len(selected) != 1:
        raise ValueError("unknown exact driveway case")
    case = selected[0]
    name = args.case.split("__")[-1]
    source = json.loads((HERE / ("diagnostic-" + name + ".json")).read_text())["files"]
    geometry = json.loads(source["original-attempt/driveway_geometry.json"])
    activity = json.loads(source["original-attempt/activity.json"])["samples"]
    road = source["road.xodr"].encode()
    image = io.BytesIO()
    Image.new("RGB", (2, 2), (240, 40, 40)).save(image, "PNG")
    png = image.getvalue()

    class Operator:
        native_attested = False
        restored = False
        closed = False

        def __init__(self):
            self.index = -1

        def geometry_packet(self, case_id):
            if case_id != geometry["case_id"]:
                raise ValueError("source case differs")
            return geometry

        def opendrive_bytes(self):
            return road

        def start(self, plan):
            self.plan = plan

        def tick(self):
            self.index += 1
            item = activity[self.index]
            return {"frame": item["frame"], "time_s": item["time_s"]}

        def activity(self, frame):
            item = activity[self.index]
            if frame != item["frame"]:
                raise ValueError("source frame differs")
            return item

        def cameras(self, frame):
            return {view: {"frame": frame, "time_s": activity[self.index]["time_s"],
                           "png": png} for view in VIEWS}

        def brake(self):
            self.braked = True

        def cleanup(self):
            self.closed = True
            self.restored = True

    target = SCRATCH / ("delivery-" + name + ("-negative" if args.negative else "-positive"))
    if target.exists():
        shutil.rmtree(target)
    original = target / "original-attempt"
    operator = Operator()
    capture(operator, case, original, diagnostic=True)
    if not operator.braked or not operator.closed or not operator.restored:
        raise ValueError("diagnostic acquisition lifecycle incomplete")
    if args.negative:
        (original / "overview.zip").unlink()
    result = audit(original, case, diagnostic=True)
    if not result["software_checks_passed"] or result["physical_completion_verified"]:
        raise ValueError("diagnostic delivery audit classification differs")
    print(json.dumps({"case_id": args.case, "software_checks_passed": True,
                      "physical_claimed": False, "actual_pixels_reviewed": False}))


if __name__ == "__main__":
    main()
