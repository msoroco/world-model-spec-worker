"""Independent CPU check of the approaching-opponent movement contrast.

Diagnostic recipes exercise this audit; they cannot establish realized Native
motion, original camera visibility or a legal result.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from approaching_yield_observation import observe as observe_yield
from approaching_no_yield_observation import observe as observe_no_yield

ROOT = Path(__file__).resolve().parent
YIELD = ROOT / 'cases/approaching_yield'
NO_YIELD = ROOT / 'cases/approaching_no_yield'
SOURCES = ('intersection_geometry.json', 'interaction_history.jsonl', 'video_frames.jsonl')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(recipe):
    recipe = Path(recipe)
    if recipe.is_dir():
        seal = json.loads((recipe / 'capture-seal.json').read_text())
        audit = json.loads((recipe / 'diagnostic-audit.json').read_text())
        if not (audit.get('software_checks_passed') is True
                and audit.get('diagnostic_fixture') is True
                and audit.get('passed') is False and audit.get('frames') == 900):
            raise ValueError('Paired full-duration diagnostic audit missing')
        if any(seal.get('sources', {}).get(name) != _sha(recipe / name)
               for name in SOURCES):
            raise ValueError('Paired original source differs from capture seal')
        if (audit.get('original_sources', {}).get('history_sha256')
                != _sha(recipe / 'interaction_history.jsonl')):
            raise ValueError('Paired original history differs from delivery audit')
        files = {name: (recipe / name).read_text() for name in SOURCES}
    else:
        files = json.loads(recipe.read_text())['files']
    if any(name not in files for name in SOURCES):
        raise ValueError('Comparison original source missing')
    return files


def _source_sha(source):
    source = Path(source)
    if source.is_file():
        return _sha(source)
    digest = hashlib.sha256()
    for name in SOURCES:
        digest.update(name.encode())
        digest.update(_sha(source / name).encode())
    return digest.hexdigest()


def _observe(files, observer):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in SOURCES:
            (root / name).write_text(files[name])
        return observer(root)


def compare(yield_recipe, no_yield_recipe):
    yfiles, nfiles = _load(yield_recipe), _load(no_yield_recipe)
    if yfiles['intersection_geometry.json'] != nfiles['intersection_geometry.json']:
        raise ValueError('Fixed junction geometry differs')
    if yfiles['video_frames.jsonl'] != nfiles['video_frames.jsonl']:
        raise ValueError('Fixed original frame map differs')
    yrows = [json.loads(line) for line in yfiles['interaction_history.jsonl'].splitlines() if line]
    nrows = [json.loads(line) for line in nfiles['interaction_history.jsonl'].splitlines() if line]
    if len(yrows) != len(nrows) or len(yrows) < 3:
        raise ValueError('Paired original sample count differs')
    for yr, nr in zip(yrows, nrows):
        if (yr['frame'], yr['time_s']) != (nr['frame'], nr['time_s']):
            raise ValueError('Paired original frame/time differs')
        for actor in ('oncoming', 'reciprocal'):
            if yr[actor] != nr[actor]:
                raise ValueError('Fixed opposing actor trajectory differs: ' + actor)
    for yr, nr in zip(yrows[:2], nrows[:2]):
        for field in ('ego', 'ego_heading_deg', 'ego_left_indicator'):
            if yr[field] != nr[field]:
                raise ValueError('Fixed pre-turn subject trajectory differs: ' + field)
    yc = json.loads((YIELD / 'config.json').read_text())
    nc = json.loads((NO_YIELD / 'config.json').read_text())
    yconstruction = json.loads((YIELD / 'construction.json').read_text())
    nconstruction = json.loads((NO_YIELD / 'construction.json').read_text())
    yfiles_construction = {item['path']: item['content'] for item in yconstruction['files']}
    nfiles_construction = {item['path']: item['content'] for item in nconstruction['files']}
    shared = set(yfiles_construction) & set(nfiles_construction)
    for path in shared - {'config.json', 'runner.py', 'finalizer.py'}:
        if yfiles_construction[path] != nfiles_construction[path]:
            raise ValueError('Fixed shared construction differs: ' + path)
    if ('from controller import LeftTurnController' not in yfiles_construction['runner.py'] or
            'from approaching_no_yield_controller import ProceedBeforeClearanceController'
            not in nfiles_construction['runner.py']):
        raise ValueError('Declared controller policy difference missing')
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'controller_release_ttc_s',
                  'approach_speed_mps', 'reciprocal_approach_speed_mps',
                  'recording_description'):
        if yc[field] != nc[field]:
            raise ValueError('Fixed construction configuration differs: ' + field)
    yobs = _observe(yfiles, observe_yield)
    nobs = _observe(nfiles, observe_no_yield)
    if not (yobs['opposing_clearance_frame'] < yobs['ego_turn_start_frame']
            and nobs['ego_turn_start_frame'] < nobs['opposing_entry_frame']):
        raise ValueError('Declared turn/clearance contrast missing')
    if yobs['initial_frame'] != nobs['initial_frame']:
        raise ValueError('Paired initial source frame differs')
    return {'format': 'c109749-approaching-comparison-diagnostic',
            'software_checks_passed': True, 'diagnostic_fixture': True,
            'delivery_passed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_asserted': False,
            'yield_case_id': yc['selected_case_id'],
            'no_yield_case_id': nc['selected_case_id'],
            'yield_construction_sha256': _sha(YIELD / 'construction.json'),
            'no_yield_construction_sha256': _sha(NO_YIELD / 'construction.json'),
            'yield_source_sha256': _source_sha(yield_recipe),
            'no_yield_source_sha256': _source_sha(no_yield_recipe),
            'source_kind': 'full_duration_diagnostic' if Path(yield_recipe).is_dir()
                           and Path(no_yield_recipe).is_dir() else 'short_diagnostic_recipe',
            'yield_turn_frame': yobs['ego_turn_start_frame'],
            'no_yield_turn_frame': nobs['ego_turn_start_frame'],
            'fixed_opposing_actor_samples': len(yrows),
            'declared_difference': 'subject yield/proceed policy and realized turn relative to opposing entry'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--yield-recipe', type=Path, default=YIELD / 'diagnostic.json')
    parser.add_argument('--no-yield-recipe', type=Path, default=NO_YIELD / 'diagnostic.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.yield_recipe, args.no_yield_recipe)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
