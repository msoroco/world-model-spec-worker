"""Prove saved release comparison and a changed fixed actor rejection."""

from hashlib import sha256
import json
from pathlib import Path
import shlex
import shutil
import tempfile

from yield_release_sweep_audit import audit


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
SOURCES = ("config.json", "intersection_topology.json", "control_inventory.json",
           "video_frames.jsonl", "trace.jsonl", "intersection_participants.jsonl",
           "subject_displacement_m.jsonl", "subject_entry_elapsed_s.jsonl")


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def selected_attempts():
    expected = digest(MANIFEST)
    roots, analyses = [], []
    for rank in range(3):
        short = f"yield_release_delay-{rank:04d}"
        proof = json.loads((HERE / (short + "-saved-proof.json")).read_text())
        if proof.get("manifest_sha256") != expected or proof.get("exit_code") != 0:
            raise ValueError("Stale selected saved release proof: " + short)
        words = shlex.split(proof["command"])
        root = Path(words[words.index("--attempt") + 1])
        if not root.is_dir():
            raise ValueError("Missing selected saved release attempt")
        roots.append(root)
        output = Path(words[words.index("--output") + 1]) / "v0001/analysis"
        if not output.is_dir():
            raise ValueError("Missing selected saved release analysis")
        analyses.append(output)
    return roots, analyses


def prove():
    attempts, analyses = selected_attempts()
    result = audit(attempts, analyses)
    result["manifest_sha256"] = digest(MANIFEST)
    result["attempts"] = [str(path) for path in attempts]
    result["analysis_roots"] = [str(path) for path in analyses]
    receipt = HERE / "yield-release-full-window-comparison-proof.json"
    receipt.write_text(json.dumps(result, indent=2) + "\n")
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as temporary:
        copies = []
        for rank, (source, analysis) in enumerate(zip(attempts, analyses)):
            target = Path(temporary) / str(rank)
            target.mkdir()
            for name in SOURCES:
                original = analysis if name.startswith("subject_") else source
                shutil.copyfile(original / name, target / name)
            copies.append(target)
        path = copies[1] / "intersection_participants.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[10]["other_corners"][0][0] += 1.0
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        try:
            audit(copies, copies)
        except ValueError as error:
            if "fixed through participant" not in str(error):
                raise
            negative = str(error)
        else:
            raise ValueError("Changed fixed through actor was accepted")
    (HERE / "yield-release-full-window-comparison-negative.log").write_text(
        negative + "\n")
    print(json.dumps({"receipt": receipt.name, "sha256": digest(receipt),
                      "points": [(row["setpoint_frames"], row["subject_entry_frame"])
                                 for row in result["points"]],
                      "negative_rejected": negative,
                      "physical_realization_claimed": False}))


if __name__ == "__main__":
    prove()
