"""Clone source geometry while varying retained synthetic lead light states."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import os

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SRC = HERE / 'selected-paragraph-d' / 'witness_1'
OUT = HERE / 'exception-1'
MANIFEST = OUT / 'manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encoded(value) + '\n')


def build_one(index, scratch):
    suffix = 'exception_1_' + str(index)
    case_id = CASE.name + '__' + suffix
    requested = index == 2
    attempt = scratch / suffix
    subprocess.run([str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
        'materialize', '--manifest', str(MANIFEST), '--case', case_id,
        '--output', str(attempt)], cwd=ROOT, capture_output=True,
        text=True, check=True, timeout=120)
    raw = [json.loads(row) for row in (SRC / 'fixture-native-raw-actors.jsonl').read_text().splitlines()]
    for row in raw:
        row['requested_lead_left_signal'] = requested
        row['observed_lead_left_blinker'] = requested
        row['observed_lead_light_state'] = 8 if requested else 0
    dest = OUT / suffix
    raw_path = dest / 'fixture-native-raw-actors.jsonl'
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(''.join(encoded(row) + '\n' for row in raw))
    spec = json.loads((SRC / 'fixture-spec.json').read_text())
    files = spec['files']
    report = json.loads(files['native-capture-report.json'])
    report['case_id'] = case_id
    report['config_sha256'] = sha(attempt / 'config.json')
    files['native-capture-report.json'] = encoded(report) + '\n'
    review = json.loads(files['review-source.json'])
    review['case_id'] = case_id
    review['raw_sha256'] = sha(raw_path)
    review['capture_report_sha256'] = hashlib.sha256(files['native-capture-report.json'].encode()).hexdigest()
    files['review-source.json'] = encoded(review) + '\n'
    spec_path = dest / 'fixture-spec.json'
    put(spec_path, spec)
    if spec_path.stat().st_size > 2097152:
        raise ValueError('Fixture spec exceeds 2 MiB')
    recipe = json.loads((SRC / 'fixture-recipe.json').read_text())
    for source in recipe['sources']:
        if source['path'] == 'native-raw-actors.jsonl':
            source['source'] = str(raw_path.relative_to(ROOT))
            source['sha256'] = sha(raw_path)
    recipe['generator'] = {'source': str(spec_path.relative_to(ROOT)),
                           'sha256': sha(spec_path)}
    recipe_path = dest / 'fixture-recipe.json'
    put(recipe_path, recipe)
    return {'case_id': case_id, 'fixture_spec_sha256': sha(spec_path),
            'fixture_recipe_sha256': sha(recipe_path)}


def build():
    scratch = Path(os.environ['TMPDIR']).resolve()
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('TMPDIR must be under .runtime-work')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='left-signal-fixtures-') as name:
        return [build_one(1, Path(name)), build_one(2, Path(name))]


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
