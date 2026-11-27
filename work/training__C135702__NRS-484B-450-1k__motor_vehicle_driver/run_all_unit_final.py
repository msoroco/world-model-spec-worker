"""Run assignment-local source, comparison, controller and Native protocol tests."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATTERNS = (
    "test_activity_controller.py", "test_statutory_variants.py",
    "test_statutory_comparison.py", "test_excavation_source.py",
    "test_native_draft.py", "test_branch_context.py",
    "test_branch_runner.py", "test_branch_comparison.py",
    "test_police_comparison_audit.py",
)


def main():
    logs = []
    for pattern in PATTERNS:
        command = [".venv-cpu/bin/python", "-B", "-m", "unittest", "discover",
                   "-s", str(ROOT / "tests"), "-p", pattern, "-v"]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        logs.append("$ " + pattern + "\n" + (result.stdout + result.stderr).rstrip() + "\n")
        if result.returncode:
            raise RuntimeError(pattern + " failed:\n" + result.stderr[-1000:])
    (ROOT / "all-unit-final.log").write_text("\n".join(logs).rstrip() + "\n")
    print("Passed", len(PATTERNS), "assignment test modules")


if __name__ == "__main__":
    main()
