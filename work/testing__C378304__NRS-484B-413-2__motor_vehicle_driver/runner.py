"""Source-gated original Native turn-signal acquisition entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil

from native_capture import capture
from native_site import read_site

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_case(case_id: str) -> dict:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    matches = [case for case in plan["cases"] if case["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("unselected exact signal case")
    return matches[0]


def execute(case_id: str, site_path: Path, site_sha256: str, output: Path,
            adapter_name: str, host: str, port: int) -> dict:
    case = selected_case(case_id)
    site = read_site(site_path, site_sha256)
    config = json.loads((ROOT / "config.json").read_text())
    if config.get("selected_case_id") != case_id:
        raise ValueError("materialized exact case differs from requested case")
    lead_samples = config.get("controller_lead_samples", 1)
    if lead_samples not in (1, 2):
        raise ValueError("unsupported source-gated controller candidate")
    case = dict(case, controller_lead_samples=lead_samples)
    if (case["target"]["signal_start_distance_ft"] not in (80, 100, 101)
            or case["target"]["weather_request"] not in ("clear", "rain")
            or case["target"]["signal_continuity_request"] not in
            ("continuous", "interrupt_then_resume")):
        raise ValueError("exact signal target differs from selected plan")
    if not output.is_dir() or any((output / name).exists() for name in
                                  ("original-site.json", "original-turn-signal.json",
                                   "original-acquisition-receipt.json", "capture-seal.json")):
        raise ValueError("original acquisition output must have no prior signal source")
    adapter = importlib.import_module(adapter_name)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Native adapter lacks open_session")
    copied_site = output / "original-site.json"
    with copied_site.open("xb") as target, Path(site_path).open("rb") as source:
        shutil.copyfileobj(source, target)
    if sha(copied_site) != site_sha256:
        raise ValueError("reviewed signal site changed during acquisition handoff")
    with adapter.open_session(host, port, {"case": case, "site": site}) as session:
        result = capture(session, site, site_sha256, case, output)
    if not session.restoration_verified:
        raise ValueError("original Native world restoration unverified")
    receipt = {"format": "original-turn-signal-acquisition",
               "case_id": case_id, "site_sha256": site_sha256,
               "trace_sha256": result["trace_sha256"],
               "frame_count": result["frame_count"],
               "camera_archives": result["camera_archives"],
               "adapter_module": adapter_name,
               "physical_acceptance": False,
               "legal_assessment": "unresolved"}
    (output / "original-acquisition-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    from saved_export import export
    from worker_exchange.native_output import seal_capture
    exported = export(output, case_id)
    seal_capture(output, frames=result["frame_count"],
                 restoration={"restored": True,
                              "settings_readback": "original settings and weather restored"},
                 errors=[], encoder_exit_codes={name: 0 for name in result["camera_archives"]},
                 context={"turn_signal_source_audit": exported["source_decode_receipt"]})
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--case-id")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--site-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--adapter", default="carla_adapter")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        config = json.loads((ROOT / "config.json").read_text())
        planned = {case["case_id"] for case in json.loads((ROOT / "case-plan.json").read_text())["cases"]}
        if (config.get("selected_case_id") not in planned or
                set(config.get("supported_case_ids", [])) != planned or
                config.get("rate_hz") != 20 or config.get("duration_s") != 45):
            raise ValueError("materialized signal case configuration differs")
        print(json.dumps({"case_id": config["selected_case_id"],
                          "source_gate": "original-site-sha256-before-adapter-import",
                          "simulation_started": False}))
        return
    config = json.loads((ROOT / "config.json").read_text())
    case_id = args.case_id or config["selected_case_id"]
    site = args.site or (Path(os.environ["SIGNAL_SITE_PATH"]) if os.environ.get("SIGNAL_SITE_PATH") else None)
    site_sha256 = args.site_sha256 or os.environ.get("SIGNAL_SITE_SHA256")
    output = args.output_dir or args.output
    if not all((case_id, site, site_sha256, output, args.adapter)):
        parser.error("original capture requires reviewed SIGNAL_SITE_PATH/SHA256 and output directory")
    try:
        print(json.dumps(execute(case_id, site, site_sha256,
                                 output, args.adapter, args.host, args.port), indent=2))
    except BaseException as error:
        if output.is_dir():
            (output / "native-run-status.json").write_text(json.dumps(
                {"errors": [repr(error)], "physical_acceptance_claimed": False}) + "\n")
        raise


if __name__ == "__main__":
    main()
