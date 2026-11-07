"""Independent saved-row and receipt audit of diagnostic fallback gates."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
proof = json.loads((HERE / 'exception-trigger-summary.json').read_text())
assert proof['format'] == 'c10316-prior-entry-synthetic-trigger-proof-v1'
assert proof['physical_triggers_observed'] == proof['accepted_recordings'] == 0
assert len(proof['records']) == 2


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clearance(folder):
    context = json.loads((folder / 'exception-context.json').read_text())
    first = json.loads((folder / 'exception-samples.jsonl').read_text().splitlines()[0])
    origin, direction = context['near_highway_edge_xy_m'], context['crossing_forward_xy']
    return round(-max(sum((v[i] - origin[i]) * direction[i] for i in (0, 1))
                      for v in first['pedestrian_footprint_xy_m']), 4)


for record in proof['records']:
    folder = Path(record['source'])
    measured = json.loads((folder / 'source-measurement.json').read_text())
    assert measured['source_sha256'] == record['baseline']['source_sha256']
    for name, digest in measured['source_sha256'].items():
        assert sha(folder / name) == digest
    baseline = record['baseline']
    assert clearance(folder) == baseline['gates']['fallback1']['observed'] == .88
    assert baseline['gates']['fallback1']['advance'] is True
    assert baseline['audit_kind'] is None and baseline['physical_triggers_observed'] is False
    farther = Path(record['more_clearance_source'])
    assert clearance(farther) == record['more_clearance']['gates']['fallback1']['observed'] == 2.88
    assert record['more_clearance']['gates']['fallback1']['advance'] is False
    assert len(record['pixel_diagnostics']) == 3
    for item in record['pixel_diagnostics']:
        audit = Path(item['audit'])
        receipt, result = json.loads(audit.read_text()), item['result']
        assert receipt['source_sha256'] == measured['source_sha256']
        assert result['pixel_audit_sha256'] == sha(audit)
        assert result['audit_kind'] == receipt['audit_kind'] == 'synthetic_diagnostic'
        assert result['physical_triggers_observed'] is False
        assert result['legal_verdict_claimed'] is False
        gates = result['gates']
        assert gates['fallback2']['observed'] == receipt['phase_skew_ms']
        assert gates['fallback2']['threshold'] == 25
        assert gates['fallback2']['advance'] is (receipt['phase_skew_ms'] > 25)
        assert gates['fallback3']['observed'] == receipt['display_legibility']
        assert gates['fallback3']['threshold'] == .95
        assert gates['fallback3']['advance'] is (receipt['display_legibility'] < .95)
    assert record['changed_source_negative'] == 'Display audit source hashes differ'
    assert record['forged_original_pixel_negative'] == 'Original pixel audit needs Native source'

print(json.dumps({'audit': 'pass', 'synthetic_cases': 2,
                  'source_bound_trigger_decisions': 8,
                  'physical_triggers_observed': 0, 'accepted_recordings': 0}))
