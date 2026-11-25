"""Bind paragraph (d) component cases to diagnostic source-shape fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = HERE / 'selected-paragraph-d'
OUT = HERE / 'exception-4'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value) + '\n')


def build_one(index, scratch):
    suffix = f'exception_4_{index}'
    source_suffix = 'witness_2' if index == 1 else 'witness_1'
    case_id = CASE.name + '__' + suffix
    attempt = scratch / suffix
    subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
        'materialize', '--manifest', str(OUT / 'manifest.json'),
        '--case', case_id, '--output', str(attempt)], cwd=ROOT,
        capture_output=True, text=True, check=True, timeout=120)
    source = SOURCE / source_suffix
    dest = OUT / suffix
    raw_path = dest / 'fixture-native-raw-actors.jsonl'
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes((source / 'fixture-native-raw-actors.jsonl').read_bytes())
    spec = json.loads((source / 'fixture-spec.json').read_text())
    files = spec['files']
    report = json.loads(files['native-capture-report.json'])
    report['case_id'] = case_id
    report['config_sha256'] = sha(attempt / 'config.json')
    files['native-capture-report.json'] = encoded(report) + '\n'
    review = json.loads(files['review-source.json'])
    review['case_id'] = case_id
    review['raw_sha256'] = sha(raw_path)
    review['capture_report_sha256'] = hashlib.sha256(
        files['native-capture-report.json'].encode()).hexdigest()
    files['review-source.json'] = encoded(review) + '\n'
    spec_path = dest / 'fixture-spec.json'
    put(spec_path, spec)
    if spec_path.stat().st_size > 2097152:
        raise ValueError('Fixture spec exceeds 2 MiB')
    recipe = json.loads((source / 'fixture-recipe.json').read_text())
    for item in recipe['sources']:
        if item['path'] == 'native-raw-actors.jsonl':
            item['source'] = str(raw_path.relative_to(ROOT))
            item['sha256'] = sha(raw_path)
    recipe['generator'] = {'source': str(spec_path.relative_to(ROOT)),
                           'sha256': sha(spec_path)}
    put(dest / 'fixture-recipe.json', recipe)
    return {'case_id': case_id, 'fixture_spec_sha256': sha(spec_path),
            'fixture_recipe_sha256': sha(dest / 'fixture-recipe.json')}


def build():
    scratch = Path(os.environ['TMPDIR']).resolve()
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('TMPDIR must be under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='paragraph-d-component-') as name:
        return [build_one(1, Path(name)), build_one(2, Path(name))]


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
