"""Independent saved audit of original U-turn camera PNGs and Native frames."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from capture_cameras import VIEWS


class SavedCameraError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise SavedCameraError(message)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(native_path: Path, native_sha256: str, manifest_path: Path,
          manifest_sha256: str, *, expected_case: str, expected_views=None,
          expected_count=900, strict_paths=None):
    """Hash and fully decode every retained original, with exact frame joins."""
    sizes = VIEWS if expected_views is None else expected_views
    if strict_paths is None:
        strict_paths = expected_count == 900
    _need(_sha(native_path) == native_sha256, "Native source hash mismatch")
    _need(_sha(manifest_path) == manifest_sha256, "camera manifest hash mismatch")
    native = json.loads(native_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    _need(native.get("case_id") == expected_case == manifest.get("case_id"),
          "case identity mismatch")
    _need(manifest.get("native_sha256") == native_sha256, "camera/Native source join mismatch")
    _need(len(native.get("frames", [])) == expected_count == manifest.get("frame_count"),
          "Native/camera frame count mismatch")
    _need(manifest.get("fps") == 20, "camera frame rate mismatch")
    _need(set(manifest.get("views", {})) == set(sizes), "camera view inventory mismatch")
    native_frames = [(row["frame"], row["time_s"]) for row in native["frames"]]
    _need(all(b[0] == a[0] + 1 and abs((b[1] - a[1]) - .05) <= .001
              for a, b in zip(native_frames, native_frames[1:])),
          "Native frame/time sequence invalid")
    evidence = {}
    for view, (width, height) in sizes.items():
        rows = manifest["views"][view]
        _need(len(rows) == expected_count, f"{view} original count mismatch")
        for (frame, time_s), row in zip(native_frames, rows):
            _need(row.get("frame") == frame and abs(row.get("time_s", -1) - time_s) <= .001,
                  f"{view} original frame/time join mismatch")
            path = Path(row["path"])
            if strict_paths and (path != manifest_path.parent / view / f"{frame:08d}.png" or
                                 not path.resolve().is_relative_to(manifest_path.parent.resolve())):
                raise SavedCameraError(f"{view} original path differs from attempt frame")
            _need(path.is_file() and path.suffix.lower() == ".png",
                  f"{view} original PNG missing")
            _need(_sha(path) == row.get("sha256"), f"{view} original hash mismatch")
            with Image.open(path) as image:
                _need(image.format == "PNG" and image.size == (width, height),
                      f"{view} original format/dimensions mismatch")
                image.load()
                _need(image.getbbox() is not None, f"{view} all-zero original pixels")
        evidence[view] = {"decoded_original_pngs": len(rows),
                          "first_frame": rows[0]["frame"],
                          "last_frame": rows[-1]["frame"]}
    return {"case_id": expected_case, "native_sha256": native_sha256,
            "camera_manifest_sha256": manifest_sha256,
            "source_decode": evidence, "physical_visibility": "unreviewed"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--native-sha256", required=True)
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--camera-sha256", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.native, args.native_sha256, args.camera_manifest,
                   args.camera_sha256, expected_case=args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
