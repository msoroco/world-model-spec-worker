"""Bind public positive and missing-source compatibility receipts, if passed."""
import hashlib
import json
from pathlib import Path
import shutil


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
manifest_path = FOLDER / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


count = 0
for entry in manifest["cases"]:
    label = entry["case_id"].rsplit("_", 1)[-1]
    for candidate_id in ("primary", "fallback1"):
        selected = entry if candidate_id == "primary" else entry["candidates"][0]
        source = REPO / ".runtime-work/c229831-temp" / f"compat-{label}-{candidate_id}-v2"
        receipt_path = source / "compatibility.json"
        if not receipt_path.is_file():
            raise ValueError("Passed compatibility receipt missing")
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get("passed") is not True or receipt.get("candidate_id") != candidate_id or
                receipt.get("case_id") != entry["case_id"] or
                receipt.get("construction_sha256") != selected["construction_sha256"] or
                receipt.get("negative_removed") != "rider_arm.jsonl"):
            raise ValueError("Compatibility receipt differs from selected source")
        target = FOLDER / "proofs" / label / candidate_id
        target.mkdir(parents=True, exist_ok=True)
        for name, renamed in (("compatibility-analysis.log", "analysis.log"),
                              ("negative-analysis.log", "negative-analysis.log"),
                              ("compatibility.json", "compatibility.json")):
            shutil.copyfile(source / name, target / renamed)
        if (sha(target / "analysis.log") != receipt["log_sha256"] or
                sha(target / "negative-analysis.log") != receipt["negative_log_sha256"]):
            raise ValueError("Copied compatibility proof log differs")
        selected["compatibility"] = {
            "receipt": (target / "compatibility.json").relative_to(FOLDER).as_posix(),
            "sha256": sha(target / "compatibility.json"),
            "log": (target / "analysis.log").relative_to(FOLDER).as_posix(),
            "negative_log": (target / "negative-analysis.log").relative_to(FOLDER).as_posix(),
        }
        selected["negative"] = {
            "log": (target / "negative-analysis.log").relative_to(FOLDER).as_posix(),
        }
        count += 1
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"bound_positive_and_negative_compatibility_receipts": count,
                  "physical_acceptance_claimed": False}))
