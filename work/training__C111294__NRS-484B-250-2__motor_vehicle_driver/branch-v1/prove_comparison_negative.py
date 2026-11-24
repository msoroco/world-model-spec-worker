"""Reject an altered actor source in the controlled turn comparison."""
import json
from pathlib import Path

from audit_sources import audit, HERE

BASE = HERE.parent
scratch = BASE.parents[1] / '.runtime-work/c111294-2502-branch-comparison-negative'
scratch.mkdir(parents=True, exist_ok=True)
history = json.loads((HERE / 'opposing_left_turn/sources/actor-history.json').read_text())
history['rows'][120]['other']['center_xyz_m'][0] += 1
path = scratch / 'altered-actor-history.json'
path.write_text(json.dumps(history, indent=2, sort_keys=True) + '\n')
audit('opposing_left_turn', path)
