"""Source-gated Native runner copied into an exact C158208 construction."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from branch_site_preflight import validate_site_branch
from carla_scene_adapter import validate_native_scene_spec
from native_attempt import verify_review_sources
from source_tick_capture import validate_geometry


def check() -> dict:
    root = Path(__file__).resolve().parent
    scene = json.loads((root / "scene.json").read_text())
    config = json.loads((root / "config.json").read_text())
    case_id = scene.get("case_id")
    if config.get("selected_case_id") != case_id or config.get("case", {}).get("kind") != scene.get("kind"):
        raise ValueError("selected case and construction scene differ")
    if scene.get("source_kind") != "original_reviewed_site":
        raise ValueError("original reviewed Native site source required")
    name = scene.get("site_source")
    if not isinstance(name, str) or Path(name).name != name or not name:
        raise ValueError("reviewed site path must be a bundled child")
    site_path = root / name
    site_bytes = site_path.read_bytes()
    if hashlib.sha256(site_bytes).hexdigest() != scene.get("site_sha256"):
        raise ValueError("reviewed Native site packet changed")
    site = json.loads(site_bytes)
    if site.get("review_status") != "reviewed" or site.get("cell_id") != "C158208":
        raise ValueError("reviewed C158208 site identity required")
    verify_review_sources(site, site_path, diagnostic_fixture=False)
    validate_site_branch(site, case_id)
    if scene.get("capture_geometry") != site.get("capture_geometry"):
        raise ValueError("reviewed capture geometry changed")
    validate_geometry(site["capture_geometry"])
    validate_native_scene_spec(site.get("native_scene"), site["capture_geometry"])
    return {"case_id": case_id, "site": site_path.name}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    selected = check()
    if args.check:
        print("source-gated offline check passed: " + selected["case_id"])
        return
    if not args.output_dir:
        raise ValueError("original Native output directory required")
    from native_capture_finalize import close_capture
    from native_attempt import run_native_attempt
    from carla_scene_adapter import CarlaSceneAdapter
    from worker_exchange import world_restore
    import carla
    root = Path(__file__).resolve().parent
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    release = run_native_attempt(client, CarlaSceneAdapter(carla), world_restore,
                                 case_id=selected["case_id"],
                                 construction=root / "construction.json",
                                 reviewed_site_packet=root / selected["site"],
                                 attempt=Path(args.output_dir))
    close_capture(Path(args.output_dir), release)


if __name__ == "__main__":
    main()
