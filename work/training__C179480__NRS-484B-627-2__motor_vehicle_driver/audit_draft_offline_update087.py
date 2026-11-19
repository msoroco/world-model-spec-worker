"""Check the three current draft exact-case offline bundles and source hashes."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE/'draft-reference-manifest.json'
CASES = ('reference', 'contrast', 'safe_operation_stop')
MODULES = ('runner.py', 'native_runner.py', 'capture_attempt.py',
           'native_finalize.py', 'native_channels.py', 'saved_analysis.py',
           'source_measurement.py', 'source_provenance.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


manifest = json.loads(MANIFEST.read_text())
require(len(manifest['cases']) == len(CASES), 'Draft exact-case coverage differs')
rows = []
for case in CASES:
    ident = HERE.name+'__'+case
    entry = next((item for item in manifest['cases'] if item['case_id'] == ident), None)
    require(entry is not None, 'Missing exact draft case: '+case)
    source = HERE/entry['construction']
    require(sha(source) == entry['construction_sha256'], 'Construction source differs')
    construction = json.loads(source.read_text())
    require(construction['case_id'] == ident and construction['entrypoint'] == 'runner.py',
            'Construction selects another exact case')
    files = {item['path']: item['content'] for item in construction['files']}
    for name in MODULES:
        require(files[name] == (HERE/name).read_text(), 'Bundled source differs: '+name)
    config = json.loads(files['config.json'])
    require(config['case_id'] == ident and config['case_suffix'] == case and
            config['frames'] == 600 and config['duration_s'] == 30,
            'Exact 30-second case config differs')
    output = ROOT/'.runtime-work/c179480-update087'/(case+'-primary-offline')
    selection = json.loads((output/'candidate-selection.json').read_text())
    require(selection['candidate_id'] == 'primary' and
            selection['construction_sha256'] == entry['construction_sha256'] and
            selection['manifest_sha256'] == sha(MANIFEST),
            'Offline selection differs from current draft manifest')
    require(json.loads((output/'construction.json').read_text()) == construction,
            'Materialized construction differs')
    log = HERE/('update087-'+('safe' if case=='safe_operation_stop' else case)+'-offline.log')
    result = json.loads(log.read_text())
    require(result['case_id'] == ident and result['offline_passed'] is True and
            result['simulation_started'] is False and
            'Ran 2 tests' in (output/'offline.log').read_text() and
            (output/'offline.log').read_text().rstrip().endswith('OK'),
            'Exact offline check incomplete')
    rows.append({'case':case, 'construction_sha256':sha(source),
                 'offline_result_log_sha256':sha(log),
                 'offline_bundle_log_sha256':sha(output/'offline.log')})
proof={'format':'c179480-three-case-draft-offline-audit-v1',
       'manifest_sha256':sha(MANIFEST),'exact_case_offline_passed':len(rows),
       'rows':rows,'compatibility_proven':False,
       'recorded_only_saved_proven':False,'original_native_accepted':False}
path=HERE/'update087-draft-offline-audit.json'
path.write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'cases':len(rows),'audit_sha256':sha(path)},sort_keys=True))
