"""Audit the selected saved attempts' measured three-point release sweep."""

from hashlib import sha256
import json
from pathlib import Path
import shlex

from qualitative_release_audit import audit


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prove():
    attempts = []
    manifest_hash = digest(MANIFEST)
    for rank in range(3):
        short = f"yield_release_delay-{rank:04d}"
        proof_path = HERE / (short + "-saved-proof.json")
        proof = json.loads(proof_path.read_text())
        if proof.get("manifest_sha256") != manifest_hash or proof.get("exit_code") != 0:
            raise ValueError("Saved release proof is stale: " + short)
        words = shlex.split(proof["command"])
        attempt = Path(words[words.index("--attempt") + 1])
        if not attempt.is_dir():
            raise ValueError("Selected saved release attempt missing: " + short)
        attempts.append(attempt)
    result = audit(attempts)
    result["manifest_sha256"] = manifest_hash
    result["attempts"] = [str(path) for path in attempts]
    path = HERE / "qualitative-release-saved-proof.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"receipt": path.name, "sha256": digest(path),
                      "points": [(row["setpoint_frames"], row["subject_entry_frame"])
                                 for row in result["points"]],
                      "physical_realization_claimed": False}))


if __name__ == "__main__":
    prove()
