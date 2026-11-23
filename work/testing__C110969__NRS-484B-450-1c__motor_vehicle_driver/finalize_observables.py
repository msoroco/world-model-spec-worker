"""Finalize original, sealed intersection observations into a nonlegal result.

Usage: python finalize_observables.py MANIFEST.json OUTPUT.json
The manifest's source paths resolve beside the manifest. It must be produced from
original map, Native trace, and independent activity/context packets.
"""

import json
import sys
from pathlib import Path

from intersection_observables import SourceError, load_source, measure


def finalize(manifest_path: Path) -> dict:
    manifest = json.loads(manifest_path.read_text())
    _case = manifest.get("case_id")
    if not isinstance(_case, str) or not _case:
        raise SourceError("missing exact case ID")
    packets = {}
    for name in ("boundary", "trace", "activity"):
        source = manifest.get(name)
        if not isinstance(source, dict) or not source.get("path") or not source.get("sha256"):
            raise SourceError(f"missing original {name} source and seal")
        path = (manifest_path.parent / source["path"]).resolve()
        if not path.is_relative_to(manifest_path.parent.resolve()):
            raise SourceError(f"original {name} source escapes attempt")
        packets[name] = load_source(path, source["sha256"])
    for name in ("trace", "activity"):
        if packets[name].get("case_id", _case) != _case:
            raise SourceError(f"original {name} case identity differs")
        if manifest.get("native_run_id") and packets[name].get("native_run_id") != manifest["native_run_id"]:
            raise SourceError(f"original {name} Native run identity differs")
    trace_frames = [row.get("frame") for row in packets["trace"].get("samples", [])]
    activity_samples = packets["activity"].get("activity_samples")
    if activity_samples is not None and [row.get("frame") for row in activity_samples] != trace_frames:
        raise SourceError("original activity/trace frame join differs")
    result = measure(packets["boundary"], packets["trace"], packets["activity"])
    return {"format": "intersection-observables-v1", "case_id": _case,
            "source_manifest": manifest_path.name, "source_seals": {
                name: manifest[name]["sha256"] for name in packets}, **result}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: finalize_observables.py MANIFEST.json OUTPUT.json")
    result = finalize(Path(sys.argv[1]).resolve())
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + "\n")
