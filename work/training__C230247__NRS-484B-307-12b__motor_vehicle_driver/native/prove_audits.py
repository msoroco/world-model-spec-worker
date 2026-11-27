"""Exercise independent source audits on diagnostic sources without acceptance."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from comparison_audit import compare_structure
from delivery_audit import ASSIGNMENT, REQUIRED, audit_structure, sha

REPO = Path(__file__).resolve().parents[3]
ROOT = Path(__file__).resolve().parents[1]
SCRATCH = REPO / '.runtime-work'
SOURCES = [SCRATCH / ('c230247-12b-probe_' + str(i) + '-compat-v4') for i in (1, 2)]

def hashes(folder):
    return {name: sha(folder / name) for name in REQUIRED}

def command(script, args, log, expected):
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'c230247-12b-audit')
    env['TMPDIR'] = str(SCRATCH)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    run = subprocess.run([sys.executable, str(ROOT / 'native' / script), *map(str, args)],
                         cwd=REPO, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, timeout=120)
    (ROOT / log).write_text(run.stdout.rstrip() + '\n')
    if expected == 'positive' and run.returncode != 0:
        raise ValueError('Positive audit failed: ' + run.stdout[-1000:])
    if expected == 'negative' and (run.returncode == 0 or
            'Original source inventory incomplete' not in run.stdout and
            'Original source hash changed' not in run.stdout):
        raise ValueError('Negative audit failed to reject source')
    return run.returncode

first, second = SOURCES
first_hashes, second_hashes = hashes(first), hashes(second)
reviews = []
for tag, attempt, digests in ((1, first, first_hashes), (2, second, second_hashes)):
    review = SCRATCH / ('c230247-12b-probe_' + str(tag) + '-audit-review.json')
    review.write_text(json.dumps({'source_sha256': digests}) + '\n')
    missing = SCRATCH / ('c230247-12b-probe_' + str(tag) + '-audit-missing-review.json')
    missing.write_text(json.dumps({'source_sha256': {name: value for name, value in digests.items()
                                                   if name != 'native-signal-rows.jsonl'}}) + '\n')
    case_id = ASSIGNMENT + '__probe_' + str(tag)
    command('delivery_audit.py', ('--case', case_id, '--attempt', attempt,
                                 '--review', review, '--structure-only'),
            'delivery-probe_' + str(tag) + '-positive.log', 'positive')
    command('delivery_audit.py', ('--case', case_id, '--attempt', attempt,
                                 '--review', missing, '--structure-only'),
            'delivery-probe_' + str(tag) + '-negative.log', 'negative')
    reviews.append(review)
command('comparison_audit.py', ('--condition-a', first, '--condition-b', second,
                                '--review-a', reviews[0], '--review-b', reviews[1], '--structure-only'),
        'comparison-positive.log', 'positive')
changed_review = SCRATCH / 'c230247-12b-comparison-changed-review.json'
changed_review.write_text(json.dumps({'source_sha256': {**second_hashes,
                                'native-map-readback.xodr': '0' * 64}}) + '\n')
command('comparison_audit.py', ('--condition-a', first, '--condition-b', second,
                                '--review-a', reviews[0], '--review-b', changed_review, '--structure-only'),
        'comparison-negative.log', 'negative')
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
