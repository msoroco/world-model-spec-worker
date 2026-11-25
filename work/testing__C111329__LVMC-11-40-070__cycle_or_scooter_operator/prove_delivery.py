"""Exercise exact-case independent delivery decode with CPU diagnostic pixels."""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_STORED

from PIL import Image

from delivery_audit import audit, CHECKS
from native_cameras import CAMERAS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
SCRATCH = REPO / ".runtime-work/c111329-delivery"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def run_one(case_id: str, negative: bool) -> dict:
    case = next(row for row in PLAN["cases"] if row["case_id"] == case_id)
    suffix = case_id.split("__")[-1]
    site = ROOT / "cases" / suffix / "diagnostic-site.json"
    source = ROOT / "cases" / suffix / "diagnostic-instruction-trace.json"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix=suffix + "-") as temporary:
        folder = Path(temporary)
        packet = json.loads(source.read_text())
        image = Image.new("RGB", (4, 4), (10, 20, 30))
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixels = buffer.getvalue()
        pixel_sha = hashlib.sha256(pixels).hexdigest()
        camera_sources = {}
        for name in CAMERAS:
            archive = folder / (name + ".png.zip")
            with ZipFile(archive, "x", compression=ZIP_STORED) as stream:
                for row in packet["samples"]:
                    member = f'{row["frame"]:08d}.png'
                    stream.writestr(member, pixels)
                    row.setdefault("camera_frames", {})[name] = {"member": member, "sha256": pixel_sha}
            camera_sources[name] = {"path": archive.name, "sha256": sha(archive),
                                    "frame_count": 900, "dimensions": [4, 4]}
        packet["camera_capture_complete"] = True
        packet["camera_sources"] = camera_sources
        trace = folder / "original-instruction-trace.json"
        dump(trace, packet)
        receipt = audit(case, site, sha(site), trace, sha(trace), diagnostic=not negative)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.case:
        print(json.dumps(run_one(args.case, args.negative), sort_keys=True))
        return
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        ident = entry["case_id"]
        suffix = ident.split("__")[-1]
        logs = []
        commands = []
        for negative in (False, True):
            command = [sys.executable, str((ROOT / "prove_delivery.py").relative_to(REPO)),
                       "--case", ident] + (["--negative"] if negative else [])
            completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log = ROOT / f"delivery-{suffix}-{'negative' if negative else 'positive'}.log"
            log.write_text((completed.stdout + completed.stderr).rstrip() + "\n")
            if negative and (completed.returncode == 0 or "diagnostic fixture cannot" not in log.read_text()):
                raise ValueError("production accepted diagnostic delivery source")
            if not negative and (completed.returncode != 0 or
                                 json.loads(completed.stdout).get("physical_acceptance") is not False):
                raise ValueError("diagnostic delivery decode failed: " + log.read_text())
            logs.append((log.name, sha(log), completed.returncode))
            commands.append(" ".join(command))
        entry["delivery_acceptance"] = {"case_id": ident, "sets": ["full-test"],
            "checks": list(CHECKS), "script": "delivery_audit.py",
            "script_sha256": sha(ROOT / "delivery_audit.py"),
            "command": commands[0], "test_exit_code": logs[0][2],
            "test_log": logs[0][0], "test_log_sha256": logs[0][1],
            "negative_command": commands[1], "negative_exit_code": logs[1][2],
            "negative_expected_error": "diagnostic fixture cannot",
            "negative_log": logs[1][0], "negative_log_sha256": logs[1][1]}
        dump(manifest_path, manifest)
        print("passed", suffix)


if __name__ == "__main__":
    main()
