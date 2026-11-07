"""Independent frozen-text and saved-source audit of d4 context requirements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
source = ROOT / 'inputs/coverage/branch-sources.json'
frozen = json.loads(source.read_text())['laws']
contract_path = HERE / 'statutory-context-contract.json'
contract = json.loads(contract_path.read_text())
proof = json.loads((HERE / 'statutory-context-summary.json').read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

assert contract['frozen_branch_source_sha256'] == sha(source)
assert len(contract['dependencies']) == 10
assert contract['cited_exact_sources_absent_from_frozen_inventory'] == ['NRS 484B.290', 'NRS 484B.350']
assert all(row['law_id'] in frozen and row['source'] == frozen[row['law_id']]['law']['source']
           and row['text_sha256'] == hashlib.sha256(frozen[row['law_id']]['law']['text'].encode()).hexdigest()
           for row in contract['dependencies'])
assert len(proof['records']) == 2
for record in proof['records']:
    path = Path(record['source_measurement'])
    measurement = json.loads(path.read_text())
    packet_path = Path(record['diagnostic_fact_packet'])
    packet = json.loads(packet_path.read_text())
    assert packet['source_sha256'] == measurement['source_sha256']
    assert packet['provenance'] == 'synthetic_diagnostic'
    for name, digest in measurement['source_sha256'].items():
        assert sha(path.parent / name) == digest
    for label, report in (('unresolved', record['unresolved']),
                          ('diagnostic_complete', record['diagnostic_complete'])):
        assert report['contract_sha256'] == sha(contract_path)
        assert report['source_measurement_sha256'] == sha(path)
        assert not report['physical_context_observed'] and not report['legal_applicability_determined']
        assert len(report['branches']) == len(contract['dependencies'])
        for branch, dependency in zip(report['branches'], contract['dependencies']):
            assert branch['law_id'] == dependency['law_id']
            assert branch['source_text_sha256'] == dependency['text_sha256']
            assert branch['required_source_facts'] == dependency['required_source_facts']
            missing = [field for field in dependency['required_source_facts']
                       if label == 'unresolved' or field not in packet['facts']]
            assert branch['missing_source_facts'] == missing
            assert branch['diagnostic_facts_complete'] is (not missing)
    assert record['diagnostic_complete']['facts_sha256'] == sha(packet_path)
    assert record['changed_source_negative'] == 'Statutory context facts source differs'

assert proof['selected_delivery_cases'] == 0
assert proof['physical_context_observed'] is False
assert proof['legal_applicability_determined'] is False
print(json.dumps({'audit': 'pass', 'exact_frozen_source_dependencies': 10,
                  'synthetic_cases': 2, 'physical_context_observed': False,
                  'legal_applicability_determined': False}))
