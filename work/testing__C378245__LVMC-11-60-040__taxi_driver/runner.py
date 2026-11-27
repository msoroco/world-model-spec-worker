"""Source-bound acquisition for the exact C378245 taxi-stand probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from native_taxi_operator import NativeTaxiOperator, read_site
from encode_taxi_views import encode_views
from taxi_stand_measurement import ASSIGNMENT, VIEWS

ROOT = Path(__file__).resolve().parent


def selected_case(config: dict) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    identity = config.get("selected_case_id")
    matches = [case for case in plan["cases"] if case.get("case_id") == identity]
    if (len(matches) != 1 or identity not in config.get("supported_case_ids", [])
            or plan.get("assignment_id") != ASSIGNMENT
            or config.get("assignment_id") != ASSIGNMENT
            or config.get("cell_id") != "C378245"
            or config.get("law_id") != "LVMC-11-60-040"
            or config.get("actor") != "taxi_driver"
            or config.get("rate_hz") != 20 or config.get("duration_s") != 45
            or set(config.get("camera_views", [])) != set(VIEWS)):
        raise ValueError("materialized taxi case/configuration differs from exact plan")
    case = matches[0]
    if (case["location_request"], case["halt_activity_request"],
            case["passenger_exchange_request"]) not in (
        ("in_stand", "park", "none"),
        ("outside_stand", "park", "none"),
        ("outside_stand", "stand", "none"),
        ("outside_stand", "temporary_stop", "loading"),
        ("outside_stand", "temporary_stop", "unloading"),
        ("outside_stand", "temporary_stop", "none")):
        raise ValueError("unselected taxi activity request")
    return case


def execute(config: dict, site_path: Path, site_sha256: str,
            output: Path, host: str, port: int) -> dict:
    case = selected_case(config)
    site = read_site(site_path, site_sha256)
    scratch = ROOT.parents[1] / ".runtime-work"
    if scratch.resolve() not in output.resolve().parents:
        raise ValueError("Native taxi attempt must be under .runtime-work")
    if not output.is_dir() or (output / "original-taxi-site.json").exists():
        raise ValueError("retain prior taxi attempt and use an empty output")
    copied = output / "original-taxi-site.json"
    copied.write_bytes(site_path.read_bytes())
    if hashlib.sha256(copied.read_bytes()).hexdigest() != site_sha256:
        raise ValueError("taxi site source changed during acquisition")
    import carla  # The original site is checked before any Native import/contact.
    client = carla.Client(host, port)
    client.set_timeout(30)
    world = client.get_world()
    operator = NativeTaxiOperator(world, carla, site)
    try:
        actors = operator.setup(case)
        captured = operator.capture(output / "native-taxi")
    finally:
        operator.close()
    encoded = encode_views(output / "native-taxi", output / "capture")
    receipt = {"format": "original-taxi-native-acquisition",
               "assignment_id": ASSIGNMENT, "case_id": case["case_id"],
               "original_site_sha256": site_sha256,
               "requested_location": case["location_request"],
               "requested_activity": case["halt_activity_request"],
               "requested_passenger_exchange": case["passenger_exchange_request"],
               "actors": actors, "capture": captured, "encoded_views": encoded,
               "passenger_activity_verified": False,
               "stand_designation_verified": False,
               "physical_acceptance": False, "legal_verdict": None}
    (output / "original-taxi-acquisition.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    args = parser.parse_args()
    config = json.loads((ROOT / "config.json").read_text())
    case = selected_case(config)
    if args.check:
        print(json.dumps({"case_id": case["case_id"],
                          "source_gate": "original taxi site SHA256 before CARLA import",
                          "simulation_started": False}))
        return
    site_path = args.site or (Path(os.environ["TAXI_SITE_PATH"])
                              if os.environ.get("TAXI_SITE_PATH") else None)
    site_sha = args.site_sha256 or os.environ.get("TAXI_SITE_SHA256")
    if args.output_dir is None or site_path is None or site_sha is None:
        parser.error("Native taxi capture requires output, TAXI_SITE_PATH and TAXI_SITE_SHA256")
    print(json.dumps(execute(config, site_path, site_sha, args.output_dir,
                             args.host, args.port), indent=2))


if __name__ == "__main__":
    main()
