"""Materializable Native draft using the retained synthetic protocol sources.

The live map readback rejects this draft until a genuine reviewed map packet is
substituted and the exact construction is re-proved. This is never delivery-ready.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from parking_pose import REQUESTS


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    cases = []
    for kind in REQUESTS:
        folder = ROOT / "diagnostic" / kind
        prior = json.loads((folder / "diagnostic-manifest.json").read_text())["cases"][0]
        def make(source_name, destination_name, approach):
            construction = json.loads((folder / source_name).read_text())
            wrapper = ('"""Source-bound CARLA-lazy C150041 Native draft."""\n'
                       'import sys\nfrom parking_runner import main\n'
                       'if __name__ == "__main__":\n'
                       '    sys.argv.extend(["--packet", "reviewed-context.json", '
                       '"--source-root", ".", "--case", "' + kind + '"' +
                       (', "--approach-distance-m", "6.0"' if approach == 6.0 else '') +
                       '])\n    main()\n')
            for item in construction["files"]:
                if item["path"] == "runner.py":
                    item["content"] = wrapper
            construction["source_kind"] = "native_draft_pending_genuine_map_activity_chapter_review"
            destination = folder / destination_name
            write(destination, construction)
            return destination
        primary = make("construction.json", "construction-native-draft.json", 8.0)
        fallback = make("construction-fallback1.json", "construction-native-draft-fallback1.json", 6.0)
        cases.append({"case_id": prior["case_id"], "kind": "native_draft_only",
                      "construction": primary.relative_to(ROOT).as_posix(),
                      "construction_sha256": sha(primary),
                      "candidate_risk": prior["candidate_risk"],
                      "candidates": [{"id": "fallback1",
                                      "construction": fallback.relative_to(ROOT).as_posix(),
                                      "construction_sha256": sha(fallback),
                                      "trigger": prior["candidates"][0]["trigger"],
                                      "changed_knobs": prior["candidates"][0]["changed_knobs"]}],
                      "preparation_status": "synthetic_source_cpu_draft_only"})
    destination = ROOT / "native-draft-manifest.json"
    write(destination, {"assignment_id": ROOT.name, "diagnostic_only": True,
                        "cases": cases})
    return destination


if __name__ == "__main__":
    print(build())
