"""Independent exact-source and receipt audit for unselected alley bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'runtime/pipeline'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(HERE/'draft-alley-execution-manifest.json')
    assert manifest['status'] == 'draft_not_selected'
    assert len(manifest['cases']) == 1
    entry = manifest['cases'][0]
    assert validate(HERE, entry, 'NRS-484B-270-3', 'C10052',
                    required=False, require_alternate=True, candidate_count=4)
    summary = read(HERE/'draft-alley-offline-summary.json')
    assert len(summary['results']) == 4
    baseline = None
    changes = []
    for receipt in summary['results']:
        ident = receipt['candidate_id']
        reference = entry if ident == 'primary' else next(
            c for c in entry['candidates'] if c['id'] == ident)
        path = HERE/reference['construction']
        assert sha(path) == reference['construction_sha256'] == receipt['construction_sha256']
        construction = read(path)
        files = {item['path']: item['content'] for item in construction['files']}
        assert len(files) == len(construction['files'])
        for source in ('alley_geometry.py', 'alley_engineering.py',
                       'measure_alley_transition.py', 'measure_alley_triggers.py',
                       'finalize_alley.py', 'finalize.py', 'measure_entry.py',
                       'measure_park_act.py'):
            assert files[source] == (HERE/'native'/source).read_text()
        assert files['runner.py'] == (HERE/'native/alley_runner.py').read_text()
        assert files['tests/test_bundle.py'] == (HERE/'tests/test_alley_bundle.py').read_text()
        config = json.loads(files['config.json'])
        assert config == json.loads(files['alley-native-config.json'])
        assert config['candidate_id'] == ident
        assert receipt['exit_code'] == 0
        assert sha(HERE/receipt['command_log']) == receipt['command_log_sha256']
        assert sha(HERE/receipt['unit_log']) == receipt['unit_log_sha256']
        unit = (HERE/receipt['unit_log']).read_text()
        assert 'Ran 4 tests' in unit and '\nOK\n' in unit
        assert 'offline' in receipt['command'] and '--candidate '+ident in receipt['command']
        if baseline is None:
            baseline = config
        else:
            invariant = ('cell_id','law_id','actor','selected_case_id','required_atoms',
                         'source_packets','rate_hz','duration_s','cameras','case')
            assert all(config[key] == baseline[key] for key in invariant)
            changed = frozenset(key for key in config if config[key] != baseline.get(key))
            assert changed == frozenset({'candidate_id'})
            assert reference['trigger']['source'] and reference['trigger']['metric']
            assert reference['trigger']['failure_condition'] and reference['changed_knobs']
            changes.append(tuple(reference['changed_knobs']))
    assert len(set(changes)) == 3
    return {'case_id': entry['case_id'], 'exact_offline_passed': 4,
            'portable_tests_per_bundle': 4, 'selected': False,
            'physical_success_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
