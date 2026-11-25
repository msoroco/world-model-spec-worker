"""Independent saved-source audit for the original motorist/rider encounter.

This checks the acquisition packet and every original camera image. It does not
substitute for composed-video decode, physical review, or a due-care judgment.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_saved(attempt, *, case_id, packet_sha256, require_attested=False,
                video_manifest_sha256=None):
    root = Path(attempt).resolve()
    packet_path = root / "encounter-packet.json"
    if not packet_path.is_file() or packet_path.is_symlink():
        raise ValueError("original encounter packet missing")
    if hashlib.sha256(packet_path.read_bytes()).hexdigest() != packet_sha256:
        raise ValueError("externally sealed encounter packet hash drift")
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("case_id") != case_id:
        raise ValueError("exact delivery case differs from original packet")
    if require_attested and packet.get("capture_origin") != "native_adapter_attested":
        raise ValueError("reviewed original Native capture adapter required")
    if packet.get("physical_review") != "pending" or packet.get("legal_judgment") != "unresolved":
        raise ValueError("acquisition packet may not assert physical or legal acceptance")
    saved = _module("saved_encounter").finalize_saved(root)
    if require_attested:
        native_ref = packet.get("native_site")
        if not native_ref:
            raise ValueError("sealed Native site survey missing")
        original = _module("native_site").verify(root, native_ref, expected_kind=saved["kind"])
        site_ref = packet["site"]
        site_path = root / site_ref["path"]
        if json.loads(site_path.read_text(encoding="utf-8")) != original:
            raise ValueError("captured site differs from sealed Native survey")
    pixels = _module("native_capture").audit_original_pixels(root)
    if saved["case_id"] != pixels["case_id"] or saved["case_id"] != case_id:
        raise ValueError("saved actor and pixel case join differs")
    if saved["original_frames"] != pixels["original_frames_per_camera"]:
        raise ValueError("saved actor and pixel frame count differs")
    video = None
    if video_manifest_sha256 is not None:
        manifest_path = root / 'video-media.json'
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise ValueError('externally sealed composed video manifest missing')
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != video_manifest_sha256:
            raise ValueError('externally sealed composed video manifest hash drift')
        video = _module('video_media').audit_composed(
            root, {'path': manifest_path.name, 'sha256': video_manifest_sha256})
        if video['case_id'] != case_id or video['original_frames'] != saved['original_frames']:
            raise ValueError('composed video and original encounter differ')
    return {
        "format": "c111260-saved-source-audit-v1",
        "case_id": case_id,
        "packet_sha256": packet_sha256,
        "original_frames": saved["original_frames"],
        "decoded_original_images": pixels["decoded_images"],
        "rider_kind": saved["kind"],
        "observed_response": saved["response"],
        "source_hashes": saved["source_hashes"],
        "media_sha256": pixels["media_sha256"],
        "full_video_decode": bool(video and video['full_video_decode']),
        "actual_pixels": False,
        "physical_completion": False,
        "legal_judgment": "unresolved",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--require-attested", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_saved(args.attempt, case_id=args.case,
                         packet_sha256=args.packet_sha256,
                         require_attested=args.require_attested)
    if args.output.exists():
        raise ValueError("saved audit output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
