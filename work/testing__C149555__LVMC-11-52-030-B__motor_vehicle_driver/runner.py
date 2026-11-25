"""Exact source-gated Native entrypoint for the six yellow-curb freight cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path

from freight_contract import SourceError, VARIANTS, read_sealed, verify_site
from finalize_original_sources import ASSIGNMENT, finalize
from native_result import write_native_result
from native_session import capture_session


ROOT = Path(__file__).resolve().parent
ORIGINALS = ("native_map", "curb_observation", "sign_observation",
             "commercial_dossier", "civil_time", "comparison_context")


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise SourceError(reason)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path = ROOT) -> dict:
    config = json.loads((Path(root) / "config.json").read_text(encoding="utf-8"))
    require(tuple(config.get(key) for key in ("assignment_id", "law_id", "cell_id", "actor")) ==
            (ASSIGNMENT, "LVMC-11-52-030-B", "C149555", "motor_vehicle_driver"),
            "wrong exact freight assignment")
    case_id = config.get("selected_case_id")
    require(case_id in {ASSIGNMENT + "__" + variant for variant in VARIANTS},
            "unknown exact freight case")
    require(set(config.get("supported_case_ids", [])) ==
            {ASSIGNMENT + "__" + variant for variant in VARIANTS},
            "six-case inventory differs")
    require(tuple(config.get(key) for key in ("rate_hz", "duration_s", "frame_count")) ==
            (20, 45, 900), "original duration or timebase differs")
    from saved_delivery import CAMERAS
    require({item.get("name"): (item.get("width"), item.get("height")) for item in
             config.get("cameras", [])} == CAMERAS, "four original camera profiles differ")
    require(config.get("case", {}).get("case_id") == case_id and
            config["case"].get("variant") == case_id.removeprefix(ASSIGNMENT + "__"),
            "selected freight variant differs")
    return config


def copy_original_sources(source_root: Path, inventory: dict, attempt: Path,
                          *, case_id: str) -> tuple[dict, dict, dict]:
    source_root = Path(source_root).resolve(strict=True)
    require(source_root.is_dir() and attempt.is_dir(), "missing original source or attempt root")
    require(inventory.get("provenance_kind") == "original_native" and
            inventory.get("diagnostic_fixture") is False and
            isinstance(inventory.get("reviewer"), str) and inventory["reviewer"].strip(),
            "reviewed original Native source provenance missing")
    references = inventory.get("sources")
    require(isinstance(references, dict) and set(ORIGINALS) <= set(references),
            "original source inventory incomplete")
    copies = {}
    target_root = attempt / "original-sources"
    target_root.mkdir(exist_ok=False)
    originals = {}
    for name in ORIGINALS:
        ref = references[name]
        path = (source_root / ref["path"]).resolve(strict=True)
        require(path.is_relative_to(source_root), "original source escapes reviewed root: " + name)
        value = read_sealed(path, ref["sha256"])
        destination = target_root / (name + ".json")
        shutil.copyfile(path, destination)
        require(sha(destination) == ref["sha256"], "original source copy drift: " + name)
        copies[name] = {"path": str(destination.relative_to(attempt)), "sha256": ref["sha256"]}
        originals[name] = value
    site_ref = inventory.get("site")
    require(isinstance(site_ref, dict) and site_ref.get("path") and site_ref.get("sha256"),
            "reviewed original site missing")
    site_path = (source_root / site_ref["path"]).resolve(strict=True)
    require(site_path.is_relative_to(source_root), "reviewed site escapes source root")
    site = read_sealed(site_path, site_ref["sha256"])
    verify_site(site)
    require(site["native_map_sha256"] == copies["native_map"]["sha256"] and
            site["curb_observation_sha256"] == copies["curb_observation"]["sha256"] and
            site["sign_observation_sha256"] == copies["sign_observation"]["sha256"],
            "reviewed site source seals differ")
    require(originals["comparison_context"].get("case_id") == case_id,
            "comparison context case differs")
    require(originals["commercial_dossier"].get("source_sha256") and
            originals["commercial_dossier"].get("enterprise_use_reviewed") is True,
            "enterprise-use dossier not independently sourced and reviewed")
    return site, originals["commercial_dossier"], copies


def run(output: Path, source_root: Path, inventory_path: Path, *, host: str,
        port: int, client_factory=None) -> dict:
    config = check()
    require(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"),
            "runtime output root must be routed to .runtime-work")
    output = Path(output)
    require(output.is_dir() and not any((output / name).exists() for name in
            ("frame-map.jsonl", "freight_motion.jsonl", "result.json",
             "freight-native-source.json", "original-sources")),
            "fresh Native attempt without prior acquisition required")
    inventory_path = Path(inventory_path).resolve(strict=True)
    source_root = Path(source_root).resolve(strict=True)
    require(inventory_path.is_relative_to(source_root), "inventory escapes reviewed source root")
    inventory = read_sealed(inventory_path, sha(inventory_path))
    case_id = config["selected_case_id"]
    site, dossier, copies = copy_original_sources(source_root, inventory, output,
                                                   case_id=case_id)
    if client_factory is None:
        import carla
        client_factory = carla.Client
    client = client_factory(host, port)
    client.set_timeout(30.0)
    capture = capture_session(client, site, dossier, case_id=case_id,
                              variant=config["case"]["variant"], output=output)
    copies["frame_map"] = {"path": "frame-index.json",
                           "sha256": sha(output / "frame-index.json")}
    source_manifest = finalize(output, case_id=case_id, source_refs=copies)
    result_path = write_native_result(output, source_manifest)
    return {"case_id": case_id, "frames": capture["frames"],
            "result_path": str(result_path), "result_sha256": sha(result_path),
            "source_manifest": source_manifest, "media": capture["media"],
            "restoration": capture["restoration"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--source-inventory", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    check()
    if args.check:
        return 0
    source_root = args.source_root or os.environ.get("C149555_SOURCE_ROOT")
    inventory = args.source_inventory or os.environ.get("C149555_SOURCE_INVENTORY")
    require(args.output_dir is not None and source_root is not None and
            inventory is not None, "reviewed original source inventory required")
    print(json.dumps(run(args.output_dir, Path(source_root), Path(inventory),
                         host=args.host, port=args.port), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
