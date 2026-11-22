"""Resolve a retained current C111256 attempt by its returned receipt hash."""
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def locate(suffix, candidate="primary"):
    receipt = HERE / "current-runtime-selected-proof" / suffix / candidate / "compatibility.json"
    if not receipt.is_file():
        raise ValueError("Current compatibility receipt missing: " + suffix + "/" + candidate)
    matches = [path for path in (ROOT / ".runtime-work").glob(
        f"c111256-current-{suffix}-{candidate}-*-compat")
        if (path / "compatibility.json").is_file() and
        sha(path / "compatibility.json") == sha(receipt)]
    if not matches:
        raise ValueError("Retained current attempt missing: " + suffix + "/" + candidate)
    return max(matches, key=lambda path: path.stat().st_mtime_ns)
