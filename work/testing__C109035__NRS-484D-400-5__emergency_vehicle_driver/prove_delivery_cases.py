"""Seven exact synthetic positive/negative independent delivery audits."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import types

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "tests"))

from camera_recorder import CAMERAS
from delivery_audit import audit
from emergency_scene import CASE_KNOBS, control_plan
from original_adapters import capture_with_original_adapters
import test_native_capture


def prove(case_id: str, *, negative: bool) -> dict:
    suffix = case_id.removeprefix(HERE.name + "__")
    if suffix == case_id or suffix not in CASE_KNOBS:
        raise ValueError("Exact delivery case required")
    base = REPO / ".runtime-work/c109035-delivery-proofs" / suffix / (
        "negative" if negative else "positive")
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    fixture = test_native_capture.CaptureTests(
        methodName="test_full_source_seal_and_distinct_command_readback")
    fixture.setUp()
    try:
        site = json.loads(fixture.site.read_text())
        site["case_id"] = case_id
        fixture.site.write_text(json.dumps(site) + "\n")
        dispatch = json.loads(fixture.dispatch.read_text())
        dispatch.update(case_id=case_id, event=CASE_KNOBS[suffix]["event"])
        fixture.dispatch.write_text(json.dumps(dispatch) + "\n")
        equipment = json.loads(fixture.equipment.read_text())
        equipment["case_id"] = case_id
        fixture.equipment.write_text(json.dumps(equipment) + "\n")
        plan = control_plan(suffix)
        instrument = fixture.folder / "original-instrument.jsonl"
        rows = []
        for tick in range(900):
            seconds = tick / 20
            siren = bool(plan["siren_command_window_s"] and
                         plan["siren_command_window_s"][0] <= seconds <=
                         plan["siren_command_window_s"][1])
            lamps = bool(plan["warning_lamp_command_window_s"] and
                         plan["warning_lamp_command_window_s"][0] <= seconds <=
                         plan["warning_lamp_command_window_s"][1])
            rows.append({"case_id": case_id, "native_frame": tick + 1,
                         "sample_id": "synthetic-independent-" + str(tick + 1),
                         "source_type": "external_device_log",
                         "source_citation": "CPU-only synthetic instrument source",
                         "siren_active": siren, "warning_lamp_active": lamps})
        instrument.write_text("".join(json.dumps(row) + "\n" for row in rows))
        image = types.SimpleNamespace(width=2, height=2,
                                      raw_data=bytes([4, 8, 16, 255] * 4))

        def camera_read(frame):
            image.frame = frame
            return {name: image for name in CAMERAS}

        def drive(ego, pedestrian, tick):
            location, rotation = ego.transform
            sign = 1 if site["approach"] == "eastbound" else -1
            ego.transform = ((site["ego_transform"]["location"][0] +
                              sign * 85 * tick / 899, location[1], location[2]),
                             rotation)

        output = base / "capture"
        receipt = capture_with_original_adapters(
            fixture.world, fixture.api, case_id=case_id,
            site_packet=fixture.site, dispatch_document=fixture.dispatch,
            equipment_document=fixture.equipment, instrument_log=instrument,
            instrument_sha256=hashlib.sha256(instrument.read_bytes()).hexdigest(),
            instrument_source_type="external_device_log",
            instrument_source_citation="CPU-only synthetic instrument source",
            output=output, device_command=lambda ego, *, siren, lamps: None,
            drive_step=drive, camera_frame_reader=camera_read,
            camera_source_ids={name: "synthetic-" + name for name in CAMERAS},
            camera_sizes={name: (2, 2) for name in CAMERAS}, diagnostic=True)
        status = {"case_id": case_id, "capture": receipt, "errors": [],
                  "restoration": {"restored": not negative},
                  "physical_acceptance_claimed": False}
        (output / "native-run-status.json").write_text(json.dumps(status) + "\n")
        result = audit(output, case_id=case_id, diagnostic_test=True)
        if negative:
            raise ValueError("Negative restoration source unexpectedly passed")
        if (result["physical_checks"]["maneuver"]["status"] != "met" or
                result["decoded_original_pixels"] != 3600 or
                result["participant_visibility_verified"] or
                result["physical_acceptance_claimed"]):
            raise ValueError("Synthetic delivery audit incomplete")
        return result
    finally:
        fixture.tearDown()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    result = prove(args.case_id, negative=args.negative)
    print(json.dumps({"case_id": result["case_id"], "frame_count": 900,
                      "diagnostic_fixture": True,
                      "independent_original_source_audit_passed": True,
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
