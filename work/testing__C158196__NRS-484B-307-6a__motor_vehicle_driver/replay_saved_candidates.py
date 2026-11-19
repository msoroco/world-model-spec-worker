"""Restage and replay every exact C158196 candidate under the current manifest."""

import base64
import hashlib
import json
import subprocess
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ARCHIVE = HERE / "saved-processing-receipts.json"
SUFFIXES = ("entry_before_red", "entry_at_red", "entry_after_red", "stops_on_yellow")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def previous_names():
    outer = json.loads(ARCHIVE.read_text())
    inner = json.loads(zlib.decompress(base64.b64decode(outer["payload"])))
    return {(row["receipt"]["case_id"], row["receipt"]["candidate_id"]):
            row["original_file"] for row in inner["receipts"]}


def run(command, log):
    result = subprocess.run(command, cwd=REPO, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, timeout=900)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout)
    if result.returncode:
        raise RuntimeError("Exact saved-only command failed: " + str(log) + " " + result.stdout[-1000:])
    return result.stdout


def main():
    names = previous_names()
    rows = []
    for suffix in SUFFIXES:
        case = HERE.name + "__" + suffix
        for candidate in CANDIDATES:
            label = suffix + "-" + candidate
            stage = [sys.executable, str(HERE / "stage_recorded_only_fixture.py"),
                     "--case", suffix, "--candidate", candidate]
            stdout = run(stage, REPO / ".runtime-work/c158196-post-capture-replay" / (label + "-stage.log"))
            attempt = json.loads(stdout)["attempt"]
            output = str(Path(attempt).parent / "processed")
            command = [sys.executable, "runtime.py", "process-saved", "--manifest",
                       str((HERE / "execution-manifest.json").relative_to(REPO)),
                       "--case", case, "--attempt", attempt, "--output", output,
                       "--library", "runtime/library", "--validator",
                       ".runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck"]
            run(command, REPO / ".runtime-work/c158196-post-capture-replay" / (label + "-saved.log"))
            receipt_path = REPO / output / "v0001/processing.json"
            original = receipt_path.read_bytes()
            receipt = json.loads(original)
            if (receipt.get("case_id") != case or receipt.get("candidate_id") != candidate or
                    receipt.get("passed") is not True or receipt.get("recorded_only") is not True or
                    receipt.get("originals_preserved") is not True or
                    receipt.get("physical_acceptance_claimed") is not False or
                    receipt.get("timestamp_joins", {}).get("frames") != 900):
                raise ValueError("Exact saved-only receipt lacks required proof: " + label)
            if original != (json.dumps(receipt, indent=2, ensure_ascii=True) + "\n").encode():
                raise ValueError("Saved-only receipt serialization changed: " + label)
            rows.append({"original_file": names[(case, candidate)],
                         "original_sha256": sha(original), "receipt": receipt})
            print(label + " passed " + sha(original), flush=True)
    raw = (json.dumps({"format": "worker-saved-processing-receipts", "receipts": rows},
                      indent=2, ensure_ascii=True) + "\n").encode()
    outer = {"format": "worker-saved-processing-receipts-compressed", "encoding": "zlib+base64",
             "uncompressed_sha256": sha(raw), "uncompressed_bytes": len(raw),
             "payload": base64.b64encode(zlib.compress(raw, 9)).decode(),
             "original_serialization": "UTF-8 json.dumps(receipt, indent=2, ensure_ascii=True) plus newline"}
    ARCHIVE.write_text(json.dumps(outer, indent=2) + "\n")
    print("archive passed " + sha(ARCHIVE.read_bytes()), flush=True)


if __name__ == "__main__":
    main()
