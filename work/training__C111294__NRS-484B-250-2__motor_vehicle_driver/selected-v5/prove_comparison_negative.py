"""Reject a controlled comparison after one other-actor body is changed."""
import importlib.util
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
SOURCE = BASE / 'selected-v3/controlled_2/primary/sources/actor-history.json'
SCRATCH = REPO / '.runtime-work/c111294-2502-comparison-negative'


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    history = json.loads(SOURCE.read_text())
    history['rows'][0]['other']['body_xyz_m'][0][0] += 0.25
    changed = SCRATCH / 'changed-history.json'
    changed.write_text(json.dumps(history) + '\n')
    module_path = BASE / 'selected-v3/audit_comparison.py'
    spec = importlib.util.spec_from_file_location('selected_comparison_audit', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.audit(changed)


if __name__ == '__main__':
    run()
