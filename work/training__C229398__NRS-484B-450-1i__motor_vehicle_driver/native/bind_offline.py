"""Bind exact selected offline probe receipts without a runtime import."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
NATIVE = Path(__file__).resolve().parent
MANIFEST = NATIVE / "selected-offline-probe-manifest.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    receipts = []
    for case in manifest["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[-1]
        for candidate in ("primary", "fallback1"):
            construction = case if candidate == "primary" else case["candidates"][0]
            source = ROOT / ".runtime-work" / f"c229398-{suffix}-{candidate}-offline9" / "attempt" / "offline.log"
            assert source.is_file(), source
            raw = source.read_text().rstrip() + "\n"
            assert '"simulation_started": false' in raw and "Ran 4 tests" in raw and raw.endswith("OK\n")
            destination = NATIVE / suffix / ("fallback1" if candidate != "primary" else "") / "offline.log"
            destination.write_text(raw)
            assert sha(NATIVE / construction["construction"]) == construction["construction_sha256"]
            receipt = {
                "case_id": case["case_id"],
                "candidate_id": candidate,
                "construction": construction["construction"],
                "construction_sha256": construction["construction_sha256"],
                "offline_exit_code": 0,
                "simulation_started": False,
                "log": str(destination.relative_to(NATIVE)),
                "log_sha256": sha(destination),
                "scope": "selected exact-case CPU offline construction; original Native run pending",
            }
            receipts.append(receipt)
    out = NATIVE / "selected-offline-proof.json"
    out.write_text(json.dumps({"format": "worker-selected-offline-proof", "receipts": receipts}, indent=2) + "\n")
    print(out.relative_to(ROOT), sha(out), len(receipts))


if __name__ == "__main__":
    main()
