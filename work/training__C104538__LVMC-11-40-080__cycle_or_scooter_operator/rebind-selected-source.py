"""Rebind selected construction source files after a reviewed Native path edit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_NAMES = ("runner.py", "finalize.py")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    selected_path = HERE / "execution-manifest.json"
    selected = json.loads(selected_path.read_text())
    draft_path = HERE / "draft-thirty-second-execution-manifest.json"
    draft = json.loads(draft_path.read_text())
    for selected_case, draft_case in zip(selected["cases"], draft["cases"]):
        if selected_case["case_id"] != draft_case["case_id"]:
            raise ValueError("Selected and draft case identities differ")
        suffix = selected_case["case_id"].rsplit("__", 1)[-1]
        selected_candidates = [(selected_case, "primary"), *(
            (candidate, candidate["id"]) for candidate in selected_case["candidates"])]
        draft_candidates = [(draft_case, "primary"), *(
            (candidate, candidate["id"]) for candidate in draft_case["candidates"])]
        for (entry, candidate_id), (draft_entry, draft_id) in zip(selected_candidates, draft_candidates):
            if candidate_id != draft_id or entry["construction"] != draft_entry["construction"]:
                raise ValueError("Selected and draft candidate identities differ")
            path = HERE / entry["construction"]
            construction = json.loads(path.read_text())
            present = set()
            for item in construction["files"]:
                if item["path"] in SOURCE_NAMES:
                    item["content"] = (HERE / item["path"]).read_text()
                    present.add(item["path"])
            if present != set(SOURCE_NAMES):
                raise ValueError("Selected bundle lacks runner or finalizer")
            write(path, construction)
            digest = sha(path)
            entry["construction_sha256"] = digest
            draft_entry["construction_sha256"] = digest
            if candidate_id == "primary":
                root = HERE if suffix == "controlled_1" else HERE / "cases" / suffix
                write(root / "construction.json", construction)
                for name in SOURCE_NAMES:
                    (root / name).write_text((HERE / name).read_text())
            for item in (entry, draft_entry):
                if "offline" in item:
                    item["offline"]["construction_sha256"] = digest
        print(suffix, [(name, entry["construction_sha256"]) for entry, name in selected_candidates])
    write(draft_path, draft)
    write(selected_path, selected)


if __name__ == "__main__":
    main()
