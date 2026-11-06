"""Persist deterministic synthetic saved-path fixtures; never original observations."""
import hashlib
import json
from pathlib import Path
from synthetic_proof import sample

HERE = Path(__file__).resolve().parent


def main():
    for suffix in ("probe_a", "probe_b"):
        target = HERE / "fixtures" / suffix / "native_samples.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(json.dumps(sample(suffix, i), separators=(",", ":")) + "\n"
                                  for i in range(480)))
        print(json.dumps({"case": suffix, "frames": 480,
                          "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                          "scope": "synthetic_cpu_only"}))


if __name__ == "__main__": main()
