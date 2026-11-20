"""Join ten existing statutory probe cases without promoting their legal status."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCES = (
    'draft-measured-candidate-manifest.json',
    'draft-barrier-capture-manifest.json',
    'draft-sign-capture-manifest.json',
    'draft-employee-capture-manifest.json',
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    planned = [row['case_id'] for row in plan['cases']]
    proposed = {row['case_id'] for row in proposals['cases']}
    assert len(planned) == len(set(planned)) == 10
    assert set(planned) == proposed
    entries = {}
    inputs = {}
    runtime_sha = None
    for name in SOURCES:
        path = HERE / name
        source = json.loads(path.read_text())
        inputs[name] = sha(path)
        assert source['assignment_id'] == HERE.name
        if runtime_sha is None:
            runtime_sha = source['runtime_manifest_sha256']
        else:
            assert runtime_sha == source['runtime_manifest_sha256']
        for entry in source['cases']:
            case_id = entry['case_id']
            assert case_id in planned and case_id not in entries
            assert entry['kind'] == 'delivery'
            assert all(entry.get(key) for key in
                       ('construction', 'construction_sha256', 'fixture_recipe',
                        'measurement_contract', 'measurement_procedure'))
            assert sha(HERE / entry['construction']) == entry['construction_sha256']
            assert [row['id'] for row in entry['candidates']] == [
                'fallback1', 'fallback2', 'fallback3']
            for candidate in entry['candidates']:
                assert sha(HERE / candidate['construction']) == candidate['construction_sha256']
            entries[case_id] = entry
    assert set(entries) == set(planned)
    combined = {
        'format': 'worker-execution-manifest',
        'assignment_id': HERE.name,
        'runtime_manifest_sha256': runtime_sha,
        'status': 'draft_combined_cpu_proof_in_progress',
        'source_manifests': inputs,
        'cases': [entries[case_id] for case_id in planned],
    }
    output = HERE / 'draft-combined-capture-manifest.json'
    output.write_text(json.dumps(combined, indent=2, sort_keys=True) + '\n')
    return {'cases': len(entries), 'candidates': sum(1 + len(row['candidates'])
            for row in entries.values()), 'manifest_sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
