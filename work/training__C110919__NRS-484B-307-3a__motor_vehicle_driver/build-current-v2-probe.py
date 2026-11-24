"""Bind both unselected circular-green diagnostics to exact source bytes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


plan = json.loads((HERE / 'case-plan.json').read_text())
manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
manifest['format'] = 'worker-unselected-current-v2-probe-manifest'
rows = [
    ('circular_green_with_arrow_activation', 'measure_signal'),
    ('right_turn_arrow_and_yield', 'measure_right_turn_permission'),
    ('opposing_red_advisory', 'measure_opposing_red_advisory'),
    ('right_turn_arrow_witness', 'measure_witness_branch'),
]
for case in ('witness_1', 'witness_2'):
    entry = next(x for x in manifest['cases'] if x['case_id'].endswith('__' + case))
    spec = json.loads((HERE / f'current-{case}-diagnostic.json').read_text())
    source = HERE / 'current-v2-source' / case
    sources = []
    for relative, content in spec['files'].items():
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Returned source file exceeds size limit: ' + relative)
        sources.append({'path': relative, 'source': str(target.relative_to(ROOT)),
                        'sha256': sha(target)})
    spec['files'] = {}
    generator = HERE / f'current-v2-{case}-generator.json'
    write(generator, spec)
    if generator.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned generator exceeds size limit')
    recipe = HERE / f'current-v2-{case}-recipe.json'
    write(recipe, {'format': 'worker-fixture-recipe', 'sources': sources,
                   'generator': {'source': str(generator.relative_to(ROOT)),
                                 'sha256': sha(generator)}})
    contract = HERE / f'current-v2-{case}-measurement-contract.json'
    dispositions = plan['requirement_dispositions']
    write(contract, {'format': 'worker-measurement-contract', 'case_id': entry['case_id'],
                     'status': 'unselected_diagnostic',
                     'requirements': [
                         {'disposition_index': i,
                          'requirement': dispositions[i]['requirement'],
                          'source': dispositions[i]['source'],
                          'output_key': key, 'method': method,
                          'value_type': 'object', 'kind': 'measured',
                          'inputs': ['native_samples.jsonl', 'road_geometry.json']}
                         for i, (key, method) in enumerate(rows)],
                     'negative': {'remove': ['road_geometry.json'],
                                  'error_contains': 'Missing required source: road_geometry.json'}})
    entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
    entry['measurement_contract'] = str(contract.relative_to(HERE))
    entry['kind'] = 'unselected_diagnostic'
    proof = HERE / 'current-v2-proofs' / case
    if (proof / 'compatibility.json').is_file():
        entry['compatibility'] = {
            'receipt': str((proof / 'compatibility.json').relative_to(HERE)),
            'sha256': sha(proof / 'compatibility.json'),
            'log': str((proof / 'analysis.log').relative_to(HERE)),
        }
write(HERE / 'current-v2-probe-manifest.json', manifest)
print(json.dumps({'manifest_sha256': sha(HERE / 'current-v2-probe-manifest.json'),
                  'cases': len(manifest['cases']), 'source_files_per_case': len(sources)}))
