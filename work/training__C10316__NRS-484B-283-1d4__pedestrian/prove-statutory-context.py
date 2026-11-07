"""Diagnostic source-binding proof for the full d4 cited-context inventory."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from statutory_context import assess

contract = HERE / 'statutory-context-contract.json'
dependencies = json.loads(contract.read_text())['dependencies']
fields = {field for row in dependencies for field in row['required_source_facts']}
records = []
for item in json.loads((HERE / 'exception-summary.json').read_text())['records']:
    folder = Path(item['retained_positive'])
    measurement_path = folder / 'source-measurement.json'
    measured = json.loads(measurement_path.read_text())
    unresolved = assess(contract, measurement_path)
    assert len(unresolved['branches']) == 10
    assert all(not row['diagnostic_facts_complete'] for row in unresolved['branches'])
    facts = {field: False for field in fields}
    facts.update(governing_pedestrian_signal=True, facing_signal=True,
                 steady_indication=True, marked_crosswalk=True,
                 walk_at_entry=measured['entry_indication'] == 'walk')
    packet = {'format': 'c10316-statutory-context-facts-v1',
              'source_sha256': measured['source_sha256'],
              'provenance': 'synthetic_diagnostic', 'facts': facts}
    facts_path = folder / 'statutory-diagnostic-facts.json'
    facts_path.write_text(json.dumps(packet, indent=2) + '\n')
    complete = assess(contract, measurement_path, facts_path)
    assert all(row['diagnostic_facts_complete'] for row in complete['branches'])
    assert not complete['legal_applicability_determined'] and not complete['physical_context_observed']
    changed_path = folder / 'statutory-changed-source.json'
    changed = dict(packet, source_sha256={})
    changed_path.write_text(json.dumps(changed, indent=2) + '\n')
    try:
        assess(contract, measurement_path, changed_path)
    except ValueError as error:
        assert 'facts source differs' in str(error)
    else:
        raise AssertionError('Changed statutory fact source accepted')
    records.append({'case_suffix': item['case_suffix'],
                    'source_measurement': str(measurement_path),
                    'diagnostic_fact_packet': str(facts_path),
                    'unresolved': unresolved, 'diagnostic_complete': complete,
                    'changed_source_negative': 'Statutory context facts source differs'})

output = {'format': 'c10316-statutory-context-cpu-proof-v1',
          'records': records, 'selected_delivery_cases': 0,
          'physical_context_observed': False, 'legal_applicability_determined': False}
(HERE / 'statutory-context-summary.json').write_text(json.dumps(output, indent=2) + '\n')
print(json.dumps({'cases': 2, 'source_dependencies': 10,
                  'diagnostic_fact_fields': len(fields), 'changed_source_rejections': 2,
                  'physical_context_observed': False, 'legal_applicability_determined': False}))
