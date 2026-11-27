"""Bind rerun public receipts after original body projection repair."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROOFS = HERE / "selected-proofs"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n")


def copy_clean(source, target):
    data = source.read_bytes()
    data.decode("utf-8")
    if any(line.rstrip(b" \t") != line for line in data.splitlines()) or \
            len(data) - len(data.rstrip(b"\n")) > 1:
        raise ValueError("Public proof has trailing whitespace: " + source.name)
    target.write_bytes(data)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Returned proof exceeds 2 MiB: " + target.name)
    return digest(target)


def bind(path):
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        physical = HERE / ("physical-preparation-" + suffix + ".json")
        if physical.is_file() and "physical_preparation" in entry:
            entry["physical_preparation"]["sha256"] = digest(physical)
        for candidate_id, selected in (("primary", entry),
                                       ("fallback1", entry["candidates"][0])):
            stem = suffix + "-" + candidate_id
            scratch = REPO / ".runtime-work" / ("c313130-projection-" + stem)
            offline = scratch.with_name(scratch.name + "-offline") / "offline.log"
            compat = scratch.with_name(scratch.name + "-compat")
            receipt = json.loads((compat / "compatibility.json").read_text())
            if (receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"] or
                    receipt.get("candidate_id") != candidate_id or
                    receipt.get("construction_sha256") != selected["construction_sha256"]):
                raise ValueError("Public compatibility differs: " + stem)
            offline_target = PROOFS / (stem + "-offline.log")
            offline_sha = copy_clean(offline, offline_target)
            selected["offline"] = {"command":
                ".venv-cpu/bin/python -B runtime.py offline --manifest work/" +
                HERE.name + "/" + ("one-way-probe-manifest.json" if suffix.startswith("one_way")
                                      else "selected-probe-manifest.json") +
                " --case " + entry["case_id"] + " --candidate " + candidate_id +
                " --output .runtime-work/c313130-projection-" + stem +
                "-offline --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "construction_sha256": selected["construction_sha256"],
                "log": str(offline_target.relative_to(HERE)),
                "log_sha256": offline_sha}
            targets = []
            for filename, ending in (("compatibility.json", "compatibility.json"),
                                     ("compatibility-analysis.log", "analysis.log"),
                                     ("negative-analysis.log", "negative.log")):
                target = PROOFS / (stem + "-" + ending)
                copy_clean(compat / filename, target)
                targets.append(target)
            selected["compatibility"] = {"receipt": str(targets[0].relative_to(HERE)),
                "sha256": digest(targets[0]),
                "log": str(targets[1].relative_to(HERE)),
                "negative_log": str(targets[2].relative_to(HERE))}
            if candidate_id == "primary":
                entry["negative"] = {"log": str(targets[2].relative_to(HERE))}
    write(path, manifest)
    return digest(path)


def main():
    for name in ("selected-probe-manifest.json", "one-way-probe-manifest.json",
                 "execution-manifest.json"):
        print(name, bind(HERE / name))


if __name__ == "__main__":
    main()
