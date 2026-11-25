"""Exact source-gated bicycle delivery entrypoint.

The local operator supplies a reviewed site adapter for its CARLA installation.
Source packets are checked before the adapter can connect or change the world.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

from native_capture import CAMERAS, PROFILE_SIZES
from signal_trial import construct_plan
from native_runner import execute_case


VARIANTS = {"two_cycles_failed_detection", "one_cycle", "three_cycles",
            "signal_changes", "no_prior_stop", "fails_to_yield"}


def check(authority_root=None, site_path=None):
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    case = config["selected_case_id"]
    entries = [row for row in json.loads(source)["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    suffix = case.removeprefix(config["assignment_id"] + "__")
    if suffix not in VARIANTS or config["case_suffix"] != suffix:
        raise ValueError("Exact red-signal variant changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    cameras = config["cameras"]
    camera_names = [camera["name"] for camera in cameras] if all(
        isinstance(camera, dict) and "name" in camera for camera in cameras
    ) else cameras
    if camera_names != list(CAMERAS) or config["camera_sizes"] != {k: list(v) for k, v in PROFILE_SIZES.items()}:
        raise ValueError("Original camera profile changed")
    if camera_names is not cameras and any(
        [camera.get("width"), camera.get("height")] != list(PROFILE_SIZES[camera["name"]])
        or not camera.get("pose_strategy") or not camera.get("fov_deg")
        for camera in cameras
    ):
        raise ValueError("Original camera pose profile changed")
    if config["required_sources"] != ["map", "device", "detector", "bicycle_blueprint", "native_trace", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    if (authority_root is None) != (site_path is None):
        raise ValueError("reviewed site and authority root must be supplied together")
    if authority_root is not None:
        site = json.loads(Path(site_path).read_text(encoding="utf-8"))
        if site.get("reviewed_original_site") is not True:
            raise ValueError("reviewed original site authority missing")
        construct_plan(site, Path(authority_root), suffix)
    return case


def run_native(*, authority_root, site_path, adapter_path, attempt_root, host, port):
    case = check(authority_root, site_path)
    site = json.loads(Path(site_path).read_text(encoding="utf-8"))
    adapter_path = Path(adapter_path).resolve()
    if not adapter_path.is_file():
        raise ValueError("reviewed local CARLA site adapter missing")
    spec = importlib.util.spec_from_file_location("reviewed_c111125_site_adapter", adapter_path)
    adapter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(adapter)
    if not callable(getattr(adapter, "connect", None)):
        raise ValueError("reviewed local CARLA site adapter lacks connect")
    bindings = adapter.connect(host=host, port=port, site=site, case_id=case)
    needed = {"world", "transform", "apply_device_policy", "apply_motion",
              "read_original", "camera_pngs"}
    if not isinstance(bindings, dict) or not needed <= set(bindings):
        raise ValueError("reviewed local CARLA site adapter lacks Native bindings")
    suffix = case.rsplit("__", 1)[-1]
    return execute_case(authority_root=authority_root, site=site,
                        case_suffix=suffix, attempt_root=attempt_root,
                        frame_count=900, diagnostic_fixture=False,
                        **{name: bindings[name] for name in needed})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print("bicycle delivery bundle passed: " + check(args.authority_root, args.site))
        return
    if not all((args.authority_root, args.site, args.adapter, args.output_dir)):
        parser.error("Native execution requires authority root, site, adapter and output directory")
    run_native(authority_root=args.authority_root, site_path=args.site,
               adapter_path=args.adapter, attempt_root=args.output_dir,
               host=args.host, port=args.port)


if __name__ == "__main__":
    main()
