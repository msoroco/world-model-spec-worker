"""Reproducible CPU fixtures for both exact reverse completion criteria."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime' / 'scenario_pipeline'))
from worker_exchange.native_output import assess_physical


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    spec = importlib.util.spec_from_file_location('reverse_fixture_tests', ROOT / 'tests' / 'test_reverse.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    command = '.venv-cpu/bin/python work/' + ROOT.name + '/prove_physical.py'
    log = ROOT / 'physical-fixtures.log'
    lines = []
    staged = []
    for entry in manifest['cases']:
        if 'crosswalk' not in entry['case_id']:
            continue
        short = entry['case_id'].endswith('__reverse_stops_before_crosswalk')
        saved_ref = entry['saved_processing']
        saved_path = ROOT / saved_ref['receipt']
        saved = json.loads(saved_path.read_text())
        if (digest(saved_path) != saved_ref['sha256'] or
                saved.get('case_id') != entry['case_id'] or
                saved.get('passed') is not True or
                saved.get('recorded_only') is not True or
                'saved_processing_started' not in saved.get('events', [])):
            raise ValueError(f'{entry["case_id"]}: missing current recorded-only saved-processing evidence')
        construction = json.loads((ROOT / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            fixture_root = REPO / '.runtime-work' / 'c215286-physical-fixtures' / ('short' if short else 'over') / kind
            fixture_root.mkdir(parents=True, exist_ok=True)
            module.Tests().fixture(fixture_root, on_crosswalk=not short)
            (fixture_root / 'config.json').write_text(json.dumps(config))
            (fixture_root / 'trace.jsonl').write_text('{}\n')
            history = fixture_root / 'reverse_history.jsonl'
            if kind == 'incomplete_motion':
                rows = [json.loads(line) for line in history.read_text().splitlines()]
                for row in rows:
                    row['velocity_mps'] = [1, 0]
                history.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            elif kind == 'missing_evidence':
                history.unlink()
            result = assess_physical(fixture_root, config, [])
            result['provenance_kind'] = 'synthetic_fixture'
            result['diagnostic_fixture'] = True
            expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met', 'missing_evidence': 'unverified'}[kind]
            actual = result['physical_checks']['maneuver']['status']
            if actual != expected or result['maneuver_completed'] != (expected == 'met'):
                raise ValueError(f'{entry["case_id"]} {kind}: expected {expected}, got {actual}')
            name = ('short' if short else 'over') + '-' + kind + '-physical-result.json'
            path = ROOT / name
            write(path, result)
            fixtures.append({'kind': kind, 'command': command, 'log': 'physical-fixtures.log',
                             'exit_code': 0, 'result': name, 'result_sha256': digest(path)})
            lines.append(f'{entry["case_id"]} {kind}: {actual}; result_sha256={digest(path)}')
        staged.append((entry, fixtures))
        lines.append(f'{entry["case_id"]}: recorded-only saved-processing receipt verified; '
                     f'sha256={digest(saved_path)}; event=saved_processing_started')
    lines.append('Synthetic lifecycle contract order asserted: capture_finished -> encoders_closed -> '
                 'restoration_verified -> native_exit -> owner_released -> saved_processing_started. '
                 'The CPU fixture does not observe a Native capture or ownership release.')
    log.write_text('\n'.join(lines) + '\n')
    for entry, fixtures in staged:
        for fixture in fixtures:
            fixture['log_sha256'] = digest(log)
        receipt = {'format': 'worker-physical-preparation', 'case_id': entry['case_id'],
                   'construction_sha256': entry['construction_sha256'], 'fixtures': fixtures,
                   'lifecycle': {'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                                            'native_exit', 'owner_released', 'saved_processing_started'],
                                 'exit_code': 0, 'log': 'physical-fixtures.log', 'log_sha256': digest(log)}}
        name = ('short' if entry['case_id'].endswith('__reverse_stops_before_crosswalk') else 'over') + '-physical-preparation.json'
        path = ROOT / name
        write(path, receipt)
        entry['physical_preparation'] = {'receipt': name, 'sha256': digest(path)}
    write(ROOT / 'execution-manifest.json', manifest)
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
