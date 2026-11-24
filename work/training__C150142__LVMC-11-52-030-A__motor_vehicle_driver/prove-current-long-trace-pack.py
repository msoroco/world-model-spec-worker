"""Verify a proposed pre-analysis transport for one synthetic long trace."""
import base64
import hashlib
import json
import tempfile
import zlib
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
INDEX = HERE / "current-tour-bus-below-trace-pack-proposal.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def expand(index, packed, destination):
    if index["source_kind"] != "synthetic_fixture":
        raise ValueError("Only synthetic fixture transport is supported")
    if sha(packed) != index["packed_sha256"]:
        raise ValueError("Packed trace source hash differs")
    raw = zlib.decompress(base64.b64decode(packed.strip(), validate=True))
    if len(raw) != index["expanded_bytes"] or sha(raw) != index["expanded_sha256"]:
        raise ValueError("Expanded trace source hash differs")
    destination.write_bytes(raw)
    return len(raw)


def main():
    index = json.loads(INDEX.read_text())
    packed = (HERE / index["packed_path"]).read_bytes()
    scratch = ROOT / ".runtime-work/owner150142"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="long-trace-pack-") as name:
        destination = Path(name) / index["source_path"]
        size = expand(index, packed, destination)
        assert sum(1 for _ in destination.open()) == index["frames"]
        changed = bytearray(packed)
        changed[0] = ord("X") if changed[0] != ord("X") else ord("Y")
        try:
            expand(index, bytes(changed), destination)
        except ValueError as exc:
            assert "Packed trace source hash differs" in str(exc)
        else:
            raise AssertionError("Changed packed source was accepted")
    print(json.dumps({"format": "c150142-long-trace-preanalysis-transport-proof-v1",
                      "case_id": index["case_id"], "source_kind": "synthetic_fixture",
                      "packed_sha256": sha(packed), "packed_bytes": len(packed),
                      "expanded_sha256": index["expanded_sha256"],
                      "expanded_bytes": size, "frames": index["frames"],
                      "changed_pack_rejected": True,
                      "official_fixture_recipe_compatibility_passed": False}, indent=2))


if __name__ == "__main__":
    main()
