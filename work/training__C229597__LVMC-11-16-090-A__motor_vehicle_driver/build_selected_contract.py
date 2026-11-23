"""Bind the exact reference requirements to source-derived CPU measurements."""
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
ASSIGNMENT = P.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    spec = P / 'selected-reference-fixture.json'
    assignment_source = ROOT / 'inputs' / ASSIGNMENT / 'assignment.json'
    write(P / 'selected-reference-recipe.json', {
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'diagnostic-assignment.json',
                     'source': assignment_source.relative_to(ROOT).as_posix(),
                     'sha256': sha(assignment_source)}],
        'generator': {'source': spec.relative_to(ROOT).as_posix(),
                      'sha256': sha(spec)}})
    plan = json.loads((P / 'case-plan.json').read_text())
    inputs = ['acquisition-provenance.json', 'trace.jsonl',
              'video_frames.jsonl', 'overview.mkv', 'approach.mkv',
              'reference_corner.mkv', 'driver_reference.mkv']
    requirements = []
    for index, key in enumerate(('text_0_motion', 'reviewed_scope_0_motion')):
        disposition = plan['requirement_dispositions'][index]
        requirements.append({
            'disposition_index': index, 'requirement': disposition['requirement'],
            'source': disposition['source'], 'output_key': key,
            'method': 'derive', 'value_type': 'object', 'kind': 'measured',
            'inputs': inputs})
    write(P / 'selected-reference-measurement-contract.json', {
        'format': 'worker-measurement-contract',
        'case_id': ASSIGNMENT + '__reference', 'requirements': requirements,
        'negative': {'remove': ['acquisition-provenance.json'],
                     'error_contains': 'Missing required source: acquisition-provenance.json'}})
    draft = json.loads((P / 'draft-primary-manifest.json').read_text())
    draft['runtime_manifest_sha256'] = sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json')
    draft['status'] = 'selected_reference_cpu_in_progress'
    entry = draft['cases'][0]
    entry['measurement_contract'] = 'selected-reference-measurement-contract.json'
    entry['fixture_recipe'] = 'work/' + ASSIGNMENT + '/selected-reference-recipe.json'
    draft['cases'] = [entry]
    write(P / 'selected-reference-manifest.json', draft)
    print(json.dumps({'recipe_sha256': sha(P / 'selected-reference-recipe.json'),
                      'contract_sha256': sha(P / 'selected-reference-measurement-contract.json'),
                      'manifest_sha256': sha(P / 'selected-reference-manifest.json')}))


if __name__ == '__main__':
    main()
