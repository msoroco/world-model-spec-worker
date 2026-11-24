"""Acquire frozen accepted video/trace bytes without substituting diagnostics.

The original absolute paths and hashes come from the SHA-verified frozen
metadata. Missing source files fail; this never creates a replacement video.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def acquire(plan: dict, repository: Path, case_id: str, recording_id: str,
            destination: Path) -> dict:
    """Copy original media into an immutable, hash-sealed local source bundle."""
    matches = [row for row in plan.get("accepted_reuse_candidates", [])
               if row.get("case_id") == case_id and row.get("recording_id") == recording_id]
    if len(matches) != 1:
        raise ValueError("exact selected recording absent from plan")
    entries = [row for row in plan.get("sources", [])
               if Path(row.get("path", "")).parts[-3:] ==
               ("accepted", recording_id, "metadata.json")]
    if len(entries) != 1:
        raise ValueError("exact frozen metadata entry absent")
    repository = Path(repository).resolve()
    rel = Path(entries[0]["path"])
    meta_path = (repository / rel).resolve()
    if rel.is_absolute() or not meta_path.is_relative_to(repository) or not meta_path.is_file():
        raise ValueError("frozen metadata source missing or escaped")
    if _sha256(meta_path) != entries[0]["sha256"]:
        raise ValueError("frozen metadata hash mismatch")
    metadata = json.loads(meta_path.read_text())
    accepted = metadata.get("acceptance", {})
    if (metadata.get("recording_id") != recording_id or metadata.get("case_id") != case_id or
            metadata.get("status") != "accepted" or metadata.get("frames") != 900 or
            accepted.get("case_id") != case_id or accepted.get("video_sha256") != metadata.get("video_sha256") or
            accepted.get("trace_sha256") != metadata.get("trace_sha256")):
        raise ValueError("frozen accepted identity or source contract mismatch")
    original = {}
    for kind, suffix in (("video", "raw.mkv"), ("trace", "trace.json")):
        source = Path(accepted.get(kind + "_source", ""))
        if (not source.is_absolute() or recording_id not in source.parts or
                source.name != suffix or not source.is_file()):
            raise ValueError(f"original {kind} source missing or outside selected recording")
        if _sha256(source) != metadata.get(kind + "_sha256"):
            raise ValueError(f"original {kind} source hash mismatch")
        original[kind] = source
    destination = Path(destination)
    if destination.exists():
        raise ValueError("refusing to overwrite acquired original source")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="original-acquisition-", dir=destination.parent) as tmp:
        root = Path(tmp)
        copied = {}
        for kind, source in original.items():
            target = root / ("raw.mkv" if kind == "video" else "trace.json")
            shutil.copyfile(source, target)
            if _sha256(target) != metadata[kind + "_sha256"]:
                raise ValueError(f"copied original {kind} hash mismatch")
            copied[kind] = {"path": target.name, "sha256": metadata[kind + "_sha256"],
                            "original_source": str(source)}
        receipt = {"format": "c129731-original-source-acquisition-v1",
                   "case_id": case_id, "recording_id": recording_id,
                   "metadata_path": str(rel), "metadata_sha256": entries[0]["sha256"],
                   "sources": copied, "original_review": "pending"}
        (root / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\n")
        root.rename(destination)
    return receipt
