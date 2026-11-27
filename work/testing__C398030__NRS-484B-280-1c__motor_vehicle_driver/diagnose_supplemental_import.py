"""Read-only diagnostic for the frozen supplemental import lookup mismatch.

This does not change the repository or certify exact delivery readiness.
"""
from pathlib import Path

from worker_exchange import portable, preparation


ASSIGNMENT = "testing__C398030__NRS-484B-280-1c__motor_vehicle_driver"


def main():
    repo = Path.cwd()
    actual_read = preparation.read
    portable_read = portable.read

    def virtual_result(path):
        value = actual_read(path)
        if Path(path) == repo / "work" / ASSIGNMENT / "result.json":
            return dict(value, status="ready", reason=None)
        return value

    def supplemental_assignment(path):
        if Path(path) == repo / "inputs" / ASSIGNMENT / "assignment.json":
            return portable_read(repo / "work" / ASSIGNMENT / "assignment.json")
        return portable_read(path)

    preparation.read = virtual_result
    portable.read = supplemental_assignment
    preparation.check(repo, assignment=ASSIGNMENT, complete=True, require_ready=True)
    print("Downstream virtual-ready checks passed with the supplemental work assignment path.")
    print("This is diagnostic only; result.json remains partial and the exact strict gate fails.")


if __name__ == "__main__":
    main()
