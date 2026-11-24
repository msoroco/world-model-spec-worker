"""Renew exact offline and diagnostic compatibility receipts after source edits."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PKG = Path(__file__).resolve().parent
MANIFEST_PATH = PKG / "execution-manifest.json"
VALIDATOR = ROOT / ".runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, capture_output=True, text=True, env=os.environ)
    log.write_text("\n".join(line.rstrip() for line in (result.stdout + result.stderr).splitlines()).rstrip() + "\n")
    if result.returncode:
        raise RuntimeError(f"proof failed ({result.returncode}): {log}")


def main():
    manifest = json.loads(MANIFEST_PATH.read_text())

    def save():
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    for entry in manifest["cases"]:
        kind = entry["case_id"].rsplit("__", 1)[1]
        for candidate in ("primary", "fallback1"):
            target = entry if candidate == "primary" else entry["candidates"][0]
            output = ROOT / ".runtime-work/c147332-site-v1-offline" / kind / candidate
            cmd = [sys.executable, str(ROOT / "runtime.py"), "offline", "--manifest",
                   str(MANIFEST_PATH), "--case", entry["case_id"], "--candidate",
                   candidate, "--output", str(output)]
            log = PKG / f"site-v1-{kind}-{candidate}-offline.log"
            run(cmd, log)
            target["offline"] = {"command": " ".join(cmd), "exit_code": 0,
                                 "construction_sha256": target["construction_sha256"],
                                 "log": log.name, "log_sha256": sha(log)}
            save()

            output = ROOT / ".runtime-work/c147332-site-v1-compat" / kind / candidate
            cmd = [sys.executable, str(ROOT / "runtime.py"), "compatibility", "--manifest",
                   str(MANIFEST_PATH), "--case", entry["case_id"], "--candidate",
                   candidate, "--output", str(output), "--library", str(ROOT / "runtime/library"),
                   "--validator", str(VALIDATOR)]
            log = PKG / f"site-v1-{kind}-{candidate}-compat-command.log"
            run(cmd, log)
            receipt = PKG / f"site-v1-{kind}-{candidate}-compat-receipt.json"
            receipt.write_bytes((output / "compatibility.json").read_bytes())
            analysis = PKG / f"site-v1-{kind}-{candidate}-compat-analysis.log"
            analysis.write_bytes((output / "compatibility-analysis.log").read_bytes())
            negative = PKG / f"site-v1-{kind}-{candidate}-compat-negative.log"
            negative.write_bytes((output / "negative-analysis.log").read_bytes())
            target["compatibility"] = {"receipt": receipt.name, "sha256": sha(receipt),
                                       "log": analysis.name, "negative_log": negative.name}
            if candidate == "primary":
                entry["negative"] = {"log": negative.name, "log_sha256": sha(negative)}
            save()
            print(kind, candidate, "offline and compatibility passed", flush=True)


if __name__ == "__main__":
    main()
