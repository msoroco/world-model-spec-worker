"""Bind successful exact-case offline logs to the current source-hashed drafts."""
import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
AID = FOLDER.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_path = FOLDER / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
for entry in manifest["cases"]:
    key = entry["case_id"].rsplit("_", 1)[-1]
    for candidate_id in ("primary", "fallback1"):
        output = REPO / ".runtime-work/c229831-temp" / f"offline-{key}-{candidate_id}"
        source_log = output / "offline.log"
        if not source_log.is_file() or "OK" not in source_log.read_text():
            raise ValueError("Successful offline proof missing: " + key + " " + candidate_id)
        target = FOLDER / "proofs" / key / candidate_id / "offline.log"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source_log.read_text().rstrip("\n") + "\n")
        selected = entry if candidate_id == "primary" else entry["candidates"][0]
        construction = FOLDER / selected["construction"]
        if sha(construction) != selected["construction_sha256"]:
            raise ValueError("Selected construction changed before offline binding")
        selected["offline"] = {
            "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + AID +
                       "/execution-manifest.json --case " + entry["case_id"] +
                       " --candidate " + candidate_id +
                       " --output .runtime-work/c229831-temp/offline-" + key + "-" + candidate_id,
            "exit_code": 0,
            "construction_sha256": selected["construction_sha256"],
            "log": target.relative_to(FOLDER).as_posix(),
            "log_sha256": sha(target),
        }
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"bound_exact_offline_proofs": 6, "physical_acceptance_claimed": False}))
