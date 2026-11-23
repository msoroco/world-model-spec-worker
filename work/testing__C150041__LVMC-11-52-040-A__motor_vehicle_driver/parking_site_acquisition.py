"""Retain an explicitly reviewed parking site against live Native map bytes.

This module imports no simulator package. The caller supplies a CARLA map after
connecting; a reviewed survey supplies the legal and activity facts. Map bytes
alone never establish a lawful direction or a Chapter exception.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import xml.etree.ElementTree as ET

from source_review import REQUIRED, validate


ASSIGNMENT = "testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _source_path(root, descriptor, name):
    if not isinstance(descriptor, dict):
        raise ValueError(name + " reviewed source descriptor required")
    relative = descriptor.get("path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(name + " reviewed source path must be local")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(name + " reviewed source missing")
    if _sha(path.read_bytes()) != descriptor.get("sha256"):
        raise ValueError(name + " reviewed source hash differs")
    if not descriptor.get("reviewer") or not descriptor.get("citation"):
        raise ValueError(name + " reviewer and citation required")
    return path


def acquire(native_map, survey_path, source_root, output_root):
    """Write an immutable attempt-local packet after checking all source joins.

    The survey is an externally reviewed declaration. ``native_map`` must be
    the current map object, whose OpenDRIVE bytes are retained verbatim. Output
    is a fresh directory; no accepted source or prior packet is overwritten.
    """
    survey_path = Path(survey_path)
    source_root = Path(source_root).resolve()
    output_root = Path(output_root)
    survey = json.loads(survey_path.read_text())
    if survey.get("assignment_id") != ASSIGNMENT or survey.get("review_status") != "reviewed":
        raise ValueError("assignment-matched reviewed survey required")
    if not survey.get("survey_reviewer") or not survey.get("survey_citation"):
        raise ValueError("survey reviewer and citation required")
    if set(survey.get("sources", {})) != set(REQUIRED) - {"roadway"}:
        raise ValueError("reviewed direction, activity and Chapter sources required")
    if not isinstance(native_map.name, str) or not native_map.name:
        raise ValueError("Native map name missing")
    xodr = native_map.to_opendrive()
    if not isinstance(xodr, str) or not xodr.strip():
        raise ValueError("Native OpenDRIVE missing")
    try:
        root = ET.fromstring(xodr)
    except ET.ParseError as exc:
        raise ValueError("Native OpenDRIVE invalid") from exc
    if root.tag != "OpenDRIVE" or not root.findall("road"):
        raise ValueError("Native OpenDRIVE road inventory missing")
    map_bytes = xodr.encode("utf-8")
    map_hash = _sha(map_bytes)
    expected = survey.get("native_map", {})
    if expected.get("name") != native_map.name or expected.get("opendrive_sha256") != map_hash:
        raise ValueError("Native map differs from reviewed survey")
    source_paths = {name: _source_path(source_root, descriptor, name)
                    for name, descriptor in survey["sources"].items()}
    context = dict(survey.get("context", {}))
    context["native_map_name"] = native_map.name
    context["native_opendrive_sha256"] = map_hash
    sources = {
        "roadway": {"path": "reviewed_sources/native-map.xodr",
                    "sha256": map_hash,
                    "reviewer": survey["survey_reviewer"],
                    "citation": survey["survey_citation"]},
    }
    for name, descriptor in survey["sources"].items():
        sources[name] = {"path": "reviewed_sources/" + name + source_paths[name].suffix,
                         "sha256": descriptor["sha256"],
                         "reviewer": descriptor["reviewer"],
                         "citation": descriptor["citation"]}
    packet = {"assignment_id": ASSIGNMENT, "review_status": "reviewed",
              "survey_sha256": _sha(survey_path.read_bytes()),
              "sources": sources, "context": context,
              "physical_realization_claimed": False,
              "legal_judgment": "unresolved"}
    output_root.parent.mkdir(parents=True, exist_ok=True)
    if output_root.exists():
        raise FileExistsError(str(output_root))
    staged = Path(tempfile.mkdtemp(prefix="parking-site-", dir=output_root.parent))
    try:
        retained = staged / "reviewed_sources"
        retained.mkdir()
        (retained / "native-map.xodr").write_bytes(map_bytes)
        for name, path in source_paths.items():
            shutil.copyfile(path, staged / sources[name]["path"])
        shutil.copyfile(survey_path, staged / "reviewed-survey.json")
        packet_path = staged / "reviewed-context.json"
        packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
        validate(packet_path, source_root=staged)
        staged.rename(output_root)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return output_root / "reviewed-context.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--survey", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / ".runtime-work").resolve()
    output = Path(args.output_dir).resolve()
    if not output.is_relative_to(scratch):
        raise ValueError("source acquisition output must be under .runtime-work")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    packet = acquire(client.get_world().get_map(), args.survey,
                     args.source_root, output)
    print(json.dumps({"packet": str(packet),
                      "sha256": _sha(packet.read_bytes()),
                      "physical_realization_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
