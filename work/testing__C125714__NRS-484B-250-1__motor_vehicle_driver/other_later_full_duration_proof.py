"""Full-duration synthetic original-source audit for later other-body entry."""
import importlib.util
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
spec = importlib.util.spec_from_file_location(
    'c125714_source_proof_base', PACKAGE / 'saved_full_duration_proof.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
proof.CASE = PACKAGE.name + '__source_verified_other_later'
proof.OUT = ROOT / '.runtime-work/c125714-other-later-full-duration'
proof.ego_x = lambda i: -4 if i < 260 else min(14, -4 + 0.08 * (i - 260))
proof.other_x = lambda i: 14 if i < 400 else max(-4, 14 - 0.08 * (i - 400))

if proof.OUT.exists():
    shutil.rmtree(proof.OUT)
attempt = proof.OUT / 'positive'
proof.write_sources(attempt)
config_path = attempt / 'config.json'
config = json.loads(config_path.read_text())
config['expected_other_enters_before_ego'] = False
config_path.write_text(json.dumps(config) + '\n')
control_path = attempt / 'controller_history.jsonl'
rows = [json.loads(line) for line in control_path.read_text().splitlines() if line.strip()]
entered = False
for i, row in enumerate(rows):
    other_inside_before = proof.inside(proof.other_x(i - 1)) if i else False
    entered = entered or other_inside_before
    row.update(ego_held=i < 260,
               other_body_inside_before_tick=other_inside_before,
               other_entered_once_before_tick=entered,
               precedence_hold=False)
control_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
analysis = proof.finalize(attempt, attempt / 'analysis-report.json')
source = analysis['source_report']
assert source['other_enters_before_ego'] is False
assert source['other_body_inside_at_ego_entry'] is False
assert source['first_body_entry']['ego']['frame'] == 1298
assert source['first_body_entry']['other']['frame'] == 1438
assert analysis['measurements']['yield_control_attempt']['value']['policy'] == 'scheduled release'
contract = json.loads((PACKAGE / 'measurement-contract.json').read_text())
verified = proof.verify_report(contract, analysis, attempt)
audit = proof.audit_delivery(attempt, PACKAGE, proof.FRAMES,
                             proof.OUT / 'independent-decoder-receipts')
assert audit['software_audit_passed'] and audit['expected_frames'] == 1100
assert all(x['decoded_frames'] == 1100 for x in audit['source_decodes'].values())
print(json.dumps({'case_id': proof.CASE, 'frames': 1100, 'rate_hz': 20,
                  'first_body_entry': source['first_body_entry'],
                  'other_enters_before_ego': False,
                  'other_body_inside_at_ego_entry': False,
                  'verified_measurements': sorted(verified),
                  'source_decodes': audit['source_decodes'],
                  'independent_delivery_audit': 'passed',
                  'diagnostic_fixture_only': True,
                  'physical_acceptance_claimed': False,
                  'legal_conclusion': 'unresolved'}, sort_keys=True))
