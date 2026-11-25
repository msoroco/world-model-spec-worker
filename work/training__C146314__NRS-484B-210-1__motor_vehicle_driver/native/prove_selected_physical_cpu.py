"""Exercise source-measured physical outcomes for every selected synthetic case."""
import hashlib
import json
from pathlib import Path

from prove_physical_lifecycle import classify, lifecycle, EVENTS


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / 'draft-selected-execution-manifest.json'
OUT = ROOT / 'native/physical-fixtures/selected'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    selected = json.loads(MANIFEST.read_text())['cases']
    receipts = []
    for entry in selected:
        case = entry['case_id']
        construction = ROOT / entry['construction']
        source = construction.parent.parent / 'fixture-native-raw-actors.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        assert len(rows) == 600
        assert all(row.get('source_kind') == 'synthetic_fixture' for row in rows)
        scenarios = {'complete_motion': (rows, 'met'),
                     'incomplete_motion': (rows[:20], 'not_met'),
                     'missing_evidence': ([{'ego': rows[0]['ego']}], 'unverified')}
        observed = {}
        case_out = OUT / case.split('__')[-1]
        case_out.mkdir(exist_ok=True)
        fixtures = []
        for name, (data, expected) in scenarios.items():
            status, evidence = classify(data)
            assert status == expected, (case, name, status)
            observed[name] = {'status': status, 'observations': evidence}
            result = {'case_id': case, 'provenance_kind': 'synthetic_fixture',
                      'diagnostic_fixture': True,
                      'physical_checks': {'maneuver': {
                          'status': status,
                          'method': 'Frame-joined ego/lead body center sequence; engineering diagnostic only',
                          'sources': [{'path': str(source.relative_to(ROOT)),
                                       'sha256': sha(source)}],
                          'observations': evidence}},
                      'maneuver_completed': status == 'met',
                      'realized_observables': evidence if status == 'met' else {},
                      'legal_verdict': None}
            result_path = case_out / (name + '-result.json')
            log_path = case_out / (name + '-test.log')
            write(result_path, result)
            log_path.write_text('PASS ' + name + ': ' + status + '; synthetic fixture only\n')
            fixtures.append({'kind': name,
                             'command': '.venv-cpu/bin/python work/' + ROOT.name +
                                        '/native/prove_selected_physical_cpu.py',
                             'exit_code': 0, 'log': str(log_path.relative_to(ROOT)),
                             'log_sha256': sha(log_path),
                             'result': str(result_path.relative_to(ROOT)),
                             'result_sha256': sha(result_path)})
        assert lifecycle(EVENTS)
        try:
            lifecycle(EVENTS[:4] + EVENTS[5:] + EVENTS[4:5])
            raise AssertionError('Saved processing preceded owner release')
        except ValueError:
            pass
        lifecycle_log = case_out / 'lifecycle-test.log'
        lifecycle_log.write_text('PASS ordered capture closure and owner release; rejected reversal\n')
        canonical = {'format': 'c146314-selected-physical-proof-v1',
                     'case_id': case, 'construction_sha256': sha(construction),
                     'fixtures': fixtures,
                     'lifecycle': {'events': EVENTS, 'exit_code': 0,
                                   'log': str(lifecycle_log.relative_to(ROOT)),
                                   'log_sha256': sha(lifecycle_log)},
                     'physical_or_legal_acceptance': False}
        proof_path = case_out / 'proof.json'
        write(proof_path, canonical)
        receipt = {'format': 'c146314-selected-physical-cpu-v1', 'case_id': case,
                   'provenance_kind': 'synthetic_fixture',
                   'source': str(source.relative_to(ROOT)), 'source_sha256': sha(source),
                   'construction': entry['construction'],
                   'construction_sha256': sha(construction),
                   'canonical_proof': str(proof_path.relative_to(ROOT)),
                   'canonical_proof_sha256': sha(proof_path),
                   'outcomes': observed, 'lifecycle_events': EVENTS,
                   'original_native_observed': False, 'physical_acceptance': False,
                   'legal_verdict': None}
        destination = OUT / (case.split('__')[-1] + '.json')
        write(destination, receipt)
        receipts.append({'case_id': case, 'path': str(destination.relative_to(ROOT)),
                         'sha256': sha(destination)})
    index = {'format': 'c146314-selected-physical-cpu-index-v1',
             'selected_case_count': len(selected), 'receipts': receipts,
             'original_native_observed': False, 'physical_acceptance': False}
    assert len(receipts) == 13
    write(OUT / 'index.json', index)
    print('PASS 13 selected synthetic source-measured three-outcome and lifecycle proofs')


if __name__ == '__main__':
    main()
