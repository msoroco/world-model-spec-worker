"""Regenerate a source-hashed U-turn diagnostic for a current-input candidate."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')


def main(case, candidate, offline):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown exact case or candidate')
    offline = Path(offline).resolve()
    native = offline / 'work' / HERE.name / 'native'
    draft = native / ('divided-opening/' if case.startswith('divided_') else '') / 'drafts' / case / candidate
    if not draft.is_dir():
        raise ValueError('Offline materialization must contain exact nested authored draft')
    source = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    config = json.loads((draft / 'config.json').read_text())
    current = sha(ROOT / 'inputs' / HERE.name / 'assignment.json')
    if config['assignment_sha256'] != current or source['law']['id'] != source['law_id']:
        raise ValueError('Candidate still binds stale migrated assignment')
    target = HERE / 'update043-current-fixtures' / case / candidate
    target.mkdir(parents=True, exist_ok=True)
    raw = target / 'raw.json'
    if raw.exists():
        raise ValueError('Retain prior raw source; use a fresh fixture version')
    module = 'saved_divided' if case.startswith('divided_') else 'saved'
    code = ('import json,sys; from pathlib import Path; '
            f'sys.path.insert(0,{str(native)!r}); from {module} import make_raw; '
            f'Path({str(raw)!r}).write_text(json.dumps(make_raw(Path({str(draft)!r})),indent=2)+"\\n")')
    subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True, timeout=30)
    old_name = f'update015-selected-{case}' + ('' if candidate == 'primary' else '-' + candidate) + '-recipe.json'
    recipe = json.loads((HERE / old_name).read_text())
    matches = [item for item in recipe['sources'] if item['path'] == 'raw.json']
    if len(matches) != 1:
        raise ValueError('Exact historical recipe lacks one raw source')
    matches[0]['source'] = str(raw.relative_to(ROOT))
    matches[0]['sha256'] = sha(raw)
    recipe_path = target / 'recipe.json'
    write(recipe_path, recipe)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == HERE.name + '__' + case)
    entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    mini = HERE / f'update043-current-manifest-{case}-{candidate}.json'
    write(mini, manifest)
    print(json.dumps({'case': case, 'candidate': candidate,
                      'assignment_sha256': current, 'raw_sha256': sha(raw),
                      'recipe_sha256': sha(recipe_path), 'manifest': str(mini.relative_to(ROOT))}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    parser.add_argument('--offline', required=True)
    args = parser.parse_args()
    main(args.case, args.candidate, args.offline)
