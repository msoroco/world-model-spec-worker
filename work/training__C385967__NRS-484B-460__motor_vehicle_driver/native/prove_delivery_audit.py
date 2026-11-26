"""Exercise independent pixel/source audit mechanics for six exact cases."""
import json
import argparse
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSIGNMENT = HERE.parent.name


def main(only=None):
    names = ("a", "b", "stop-a", "stop-b", "stand-a", "stand-b")
    if only is not None and only not in names:
        raise ValueError("Unknown exact case")
    for name in ((only,) if only else names):
        action, letter = name.split("-", 1) if "-" in name else ("park", name)
        suffix = "" if action == "park" else action + "_"
        case = ASSIGNMENT + "__selected_03f318de__" + suffix + "condition_" + letter
        fixture = ROOT / ".runtime-work" / (f"c385967-{name}-primary-compat" if action != "park"
                                              else f"c385967-{name}-primary-compat4")
        if not (fixture / "compatibility.json").is_file():
            raise ValueError("Public compatibility fixture missing: " + name)
        for mode, expected in (("--selftest", 0), ("--negative-selftest", 1)):
            result = subprocess.run([sys.executable, "-B", str(HERE / "delivery_audit.py"),
                "--case", case, mode, "--fixture", str(fixture)], cwd=ROOT,
                capture_output=True, text=True, timeout=900)
            log = HERE / f"delivery-{name}-{'positive' if expected == 0 else 'negative'}.log"
            log.write_text((result.stdout + result.stderr).rstrip() + "\n")
            if result.returncode != expected:
                raise ValueError("Delivery audit exit code differs: " + name + " " + mode)
            if expected == 0 and json.loads(result.stdout).get("passed") is not True:
                raise ValueError("Delivery audit positive did not pass")
            if expected == 1 and "Reviewed pixel box exceeds source video" not in result.stderr:
                raise ValueError("Delivery audit wrong negative reason")
        print(json.dumps({"case_id": case, "audit_positive": True,
                          "invalid_pixel_box_rejected": True}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--name")
    args = parser.parse_args()
    main(args.name)
