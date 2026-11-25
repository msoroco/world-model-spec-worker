"""Source-gated original Native turn-signal acquisition entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
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
    if (case["target"]["signal_start_distance_ft"] not in (80, 100, 101)
            or case["target"]["weather_request"] not in ("clear", "rain")
            or case["target"]["signal_continuity_request"] not in
            ("continuous", "interrupt_then_resume")):
        raise ValueError("exact signal target differs from selected plan")
    if not output.is_dir() or any(output.iterdir()):
        raise ValueError("original acquisition output must be an empty directory")
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
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--site-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    print(json.dumps(execute(args.case_id, args.site, args.site_sha256,
                             args.output, args.adapter, args.host, args.port), indent=2))


if __name__ == "__main__":
    main()
