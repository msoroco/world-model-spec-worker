"""Exercise independent source audits on diagnostic sources without acceptance."""
import json
import shutil
import tempfile
from pathlib import Path

from comparison_audit import compare_structure
from delivery_audit import ASSIGNMENT, REQUIRED, audit_structure, sha

REPO = Path(__file__).resolve().parents[3]
SCRATCH = REPO / '.runtime-work'
SOURCES = [SCRATCH / ('c230247-12b-probe_' + str(i) + '-compat-v2') for i in (1, 2)]

def hashes(folder):
    return {name: sha(folder / name) for name in REQUIRED}

first, second = SOURCES
first_hashes, second_hashes = hashes(first), hashes(second)
left = audit_structure(first, ASSIGNMENT + '__probe_1', first_hashes)
right = audit_structure(second, ASSIGNMENT + '__probe_2', second_hashes)
assert left['governed_lane_overlap_frames'] == 0
assert right['governed_lane_overlap_frames'] > 0
positive = compare_structure(first, second, first_hashes, second_hashes)
assert positive['passed'] and all(positive['fixed_checks'].values())
try:
    audit_structure(first, ASSIGNMENT + '__probe_1', {k: v for k, v in first_hashes.items()
                                                      if k != 'native-signal-rows.jsonl'})
except ValueError as exc:
    assert 'inventory incomplete' in str(exc)
else:
    raise AssertionError('missing original signal source accepted')
with tempfile.TemporaryDirectory(prefix='c230247-12b-audit-', dir=SCRATCH) as temp:
    changed = Path(temp)
    for name in ('config.json', *REQUIRED):
        target = changed / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(second / name, target)
    cfg = json.loads((changed / 'config.json').read_text())
    cfg['duration_s'] = 29
    (changed / 'config.json').write_text(json.dumps(cfg) + '\n')
    try:
        compare_structure(first, changed, first_hashes, hashes(changed))
    except ValueError as exc:
        assert 'Fixed actor, duration' in str(exc)
    else:
        raise AssertionError('changed fixed duration accepted')
print(json.dumps({'passed': True, 'positive_cases': 2,
                  'negative_missing_source_inventory': True,
                  'negative_changed_fixed_duration': True,
                  'physical_acceptance_claimed': False}, sort_keys=True))
