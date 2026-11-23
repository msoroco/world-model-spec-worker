"""Exact advance-case synthetic source proof; no Native or legal acceptance."""
import importlib.util
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
spec = importlib.util.spec_from_file_location(
    'c125714_shared_source_proof', PACKAGE / 'saved_full_duration_proof.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
proof.CASE = PACKAGE.name + '__source_verified_advance'
proof.OUT = ROOT / '.runtime-work/c125714-advance-full-duration'
proof.ego_x = lambda i: -4 if i < 260 else min(14, -4 + 0.08 * (i - 260))
proof.other_x = lambda i: 14 if i < 200 else max(-4, 14 - 0.08 * (i - 200))
original_write_sources = proof.write_sources


def write_advance_sources(attempt):
    original_write_sources(attempt)
    controller = attempt / 'controller_history.jsonl'
    rows = [json.loads(line) for line in controller.read_text().splitlines() if line.strip()]
    for i, row in enumerate(rows):
        row['precedence_hold'] = False
        row['ego_held'] = i < 260
    controller.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


proof.write_sources = write_advance_sources
proof.main()
analysis = json.loads((proof.OUT / 'positive/analysis-report.json').read_text())
source = analysis['source_report']
assert source['other_enters_before_ego'] is True
assert source['other_body_inside_at_ego_entry'] is True
assert source['first_body_entry']['other']['frame'] == 1238
assert source['first_body_entry']['ego']['frame'] == 1298
print(json.dumps({'case_id': proof.CASE,
                  'other_entry_frame': 1238, 'ego_entry_frame': 1298,
                  'other_inside_at_ego_entry': True,
                  'source_report_sha256': hashlib.sha256((proof.OUT / 'positive/analysis-report.json').read_bytes()).hexdigest(),
                  'diagnostic_fixture_only': True,
                  'physical_acceptance_claimed': False}, sort_keys=True))
