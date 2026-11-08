"""Independent exact-bundle audit of selected statutory measurement diagnostics."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    0: ('immediate_approach_context', 'measure_immediate_approach'),
    2: ('shoulder_sign_exception', 'measure_shoulder_sign_exception'),
    9: ('transit_bus_exception', 'measure_transit_bus_exception'),
    10: ('right_edge_position', 'measure_right_edge'),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    contract = read(HERE / 'native/selected-measurement-contract.json')
    plan = read(HERE / 'case-plan.json')
    manifest = read(HERE / 'draft-execution-manifest.json')
    proof = read(HERE / 'exact-finalization-proof.json')
    assert contract['format'] == 'worker-measurement-contract-v1'
    assert contract['negative'] == {
        'remove': ['actor-frames.jsonl'],
        'error_contains': 'Missing required source: actor-frames.jsonl'}
    assert set(EXPECTED) == {r['disposition_index'] for r in contract['requirements']}
    for row in contract['requirements']:
        index = row['disposition_index']
        disposition = plan['requirement_dispositions'][index]
        assert disposition['status'] == 'selected_required'
        assert (row['requirement'], row['source']) == (
            disposition['requirement'], disposition['source'])
        assert (row['output_key'], row['method']) == EXPECTED[index]
        assert row['inputs'] == ['source-scope.json', 'actor-frames.jsonl']
    assert proof['manifest_sha256'] == sha(HERE / 'draft-execution-manifest.json')
    assert len(proof['results']) == 8
    audited = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        assert entry['measurement_contract'] == 'native/selected-measurement-contract.json'
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE / 'draft-candidates' / case / candidate
            record = next(r for r in proof['results'] if r['case_id'] == entry['case_id']
                          and r['candidate_id'] == candidate)
            report = read(folder / 'finalization-analysis.json')
            result = read(folder / 'finalization-result.json')
            assert record['analysis_sha256'] == sha(folder / 'finalization-analysis.json')
            assert record['result_sha256'] == sha(folder / 'finalization-result.json')
            assert record['measurement_negative_log_sha256'] == sha(folder / 'measurement-negative.log')
            assert contract['negative']['error_contains'] in (folder / 'measurement-negative.log').read_text()
            assert report['case_id'] == result['case_id'] == entry['case_id']
            assert not result['accepted'] and not result['setup_confirmed']
            assert not report['physical_acceptance_claimed'] and not report['legal_verdict_claimed']
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            values = report['measurements']
            assert set(EXPECTED.values()) == {(k, values[k]['method']) for k, _ in EXPECTED.values()}
            sources = values['right_edge_position']['sources']
            assert set(sources) == {'source-scope.json', 'actor-frames.jsonl'}
            for key, method in EXPECTED.values():
                item = values[key]
                assert item['method'] == method and item['sources'] == sources
                assert isinstance(item['value'], dict) and item['value']['source_kind'] == 'synthetic_cpu'
            assert values['immediate_approach_context']['value']['authority_verified'] is False
            assert values['immediate_approach_context']['value']['qualifying_lamps_verified'] is False
            assert values['immediate_approach_context']['value']['officer_direction_reviewed'] is False
            assert values['shoulder_sign_exception']['value']['lawful_shoulder_sign_verified'] is False
            assert values['transit_bus_exception']['value']['public_transit_bus_identity_verified'] is False
            assert values['transit_bus_exception']['value']['signed_shoulder_use_verified'] is False
            assert values['right_edge_position']['value']['edge_before_catchup'] == (case == 'reference')
            assert values['right_edge_position']['value']['as_close_as_possible_verified'] is False
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'analysis_sha256': record['analysis_sha256'],
                            'source_hashes': sources})
    output = {'format': 'c405647-1b-independent-selected-measurement-audit-v1',
              'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
              'contract_sha256': sha(HERE / 'native/selected-measurement-contract.json'),
              'rows': audited, 'original_native_or_delivery_ready_claimed': False}
    (HERE / 'selected-measurement-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['rows'])}))
