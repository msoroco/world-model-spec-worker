"""Exercise the independent source comparison and altered-source rejections."""
import json
from pathlib import Path
import tempfile

from audit import audit
from prove import make_source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def write_rows(path, values):
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values))


def reject(first, second, path, mutate, expected):
    original = path.read_text()
    try:
        values = [json.loads(line) for line in original.splitlines() if line.strip()]
        mutate(values)
        write_rows(path, values)
        try:
            audit(first, second)
        except ValueError as exc:
            if expected not in str(exc):
                raise AssertionError(str(exc)) from exc
            return {"mutation": expected, "error": str(exc)}
        raise AssertionError("Altered source comparison accepted: " + expected)
    finally:
        path.write_text(original)


def run():
    ROOT.joinpath(".runtime-work").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c109028-comparison-") as folder:
        base = Path(folder)
        pa, pb = base / "probe_a", base / "probe_b"
        pa.mkdir()
        pb.mkdir()
        a, b = make_source(pa, "probe_a"), make_source(pb, "probe_b")
        positive = audit(a, b)
        negatives = [
            reject(a, b, b[1], lambda x: x[150].update(warning_lamp_observed=False),
                   "Matched native motion, signals or video joins differ"),
            reject(a, b, b[2], lambda x: x[100].update(time_s=10.0),
                   "Retained frame/time join differs"),
            reject(a, b, b[3], lambda x: x[150].update(emergency_call_documented=True),
                   "Documented emergency-call contrast differs"),
            reject(a, b, b[3], lambda x: x[150].update(immediate_pursuit_documented=True),
                   "Dispatch source fields other than call status differ"),
        ]
    result = {"format": "c109028-source-comparison-proof-v1",
              "positive": positive, "negatives": negatives,
              "original_native_observed": False, "physical_legal_verdict": None}
    (HERE / "comparison-proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return {"positive": 1, "negatives": len(negatives)}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
