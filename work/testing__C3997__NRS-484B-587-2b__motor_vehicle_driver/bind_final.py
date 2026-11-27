"""Bind the current CPU proof receipts to the exact delivery manifest."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

from author_semantic import AID, HERE


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def check_binding(path: Path, expected: str) -> None:
    if digest(path) != expected:
        raise ValueError(f"Proof binding changed: {path}")


def main() -> None:
    manifest = json.loads((HERE / "execution-manifest.delivery-draft.json").read_text())
    if manifest["assignment_id"] != AID or len(manifest["cases"]) != 10:
        raise ValueError("Exact case inventory changed")
    for entry in manifest["cases"]:
        check_binding(HERE / entry["construction"], entry["construction_sha256"])
        check_binding(HERE / entry["offline"]["log"], entry["offline"]["log_sha256"])
        check_binding(HERE / entry["compatibility"]["receipt"], entry["compatibility"]["sha256"])
        check_binding(HERE / entry["post_capture"]["test_log"], entry["post_capture"]["test_log_sha256"])
        check_binding(HERE / entry["physical_preparation"]["receipt"], entry["physical_preparation"]["sha256"])
        delivery = entry["delivery_acceptance"]
        check_binding(HERE / delivery["script"], delivery["script_sha256"])
        check_binding(HERE / delivery["test_log"], delivery["test_log_sha256"])
        check_binding(HERE / delivery["negative_log"], delivery["negative_log_sha256"])
        for candidate in entry["candidates"]:
            check_binding(HERE / candidate["construction"], candidate["construction_sha256"])
            check_binding(HERE / candidate["offline"]["log"], candidate["offline"]["log_sha256"])
            check_binding(HERE / candidate["compatibility"]["receipt"], candidate["compatibility"]["sha256"])
    manifest["status"] = "cpu_proven_diagnostic_package"
    for entry in manifest["cases"]:
        entry["status"] = "cpu_proven_diagnostic_delivery"
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "exact cases")


if __name__ == "__main__":
    main()
