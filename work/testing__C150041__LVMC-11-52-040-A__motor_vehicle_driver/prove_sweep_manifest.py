"""Run exact pinned offline and compatibility proof for selected sweep cases."""
from pathlib import Path

import prove_execution_manifest as proof
from parking_pose import SWEEP_REQUESTS


proof.MANIFEST = Path(__file__).resolve().parent / 'sweep-manifest-draft.json'
proof.REQUESTS = SWEEP_REQUESTS


if __name__ == '__main__':
    proof.main()
