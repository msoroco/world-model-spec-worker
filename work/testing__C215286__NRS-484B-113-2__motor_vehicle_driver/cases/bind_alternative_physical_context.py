"""Bind alternative physical completion to its original site context.

The pinned default for NRS 484B.113(2) names crosswalk_context.json.  The
intersection and corner constructions instead capture reverse_site_context.json.
This script edits only the four staged construction bundles and their manifest
hashes; it does not select or claim readiness for them.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "alternative-offline-manifest.json"


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        path = ROOT / entry["construction"]
        bundle = json.loads(path.read_text())
        config_file = next(item for item in bundle["files"] if item["path"] == "config.json")
        config = json.loads(config_file["content"])
        config["physical_completion"] = {
            "context_sources": ["reverse_site_context.json"],
        }
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        path.write_text(json.dumps(bundle, indent=2) + "\n")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entry["construction_sha256"] = digest
        entry["offline"]["construction_sha256"] = digest
        print(entry["case_id"], digest)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
