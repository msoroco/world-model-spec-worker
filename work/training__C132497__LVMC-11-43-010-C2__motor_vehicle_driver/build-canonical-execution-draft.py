"""Bind existing selected CPU proofs without claiming Native delivery acceptance."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import sys
    sys.path.insert(0, str(REPO/'runtime/pipeline'))
    from scenario_pipeline.worker_exchange.candidate_constructions import validate
    from scenario_pipeline.worker_exchange.delivery_handoff import validate_case

    source = read(ROOT/'execution-manifest.json')
    offline_rows = {(r['case_id'], r['candidate_id']): r for r in
                    read(ROOT/'update015-selected-offline-matrix.json')['results']}
    compatibility_rows = {(r['case_id'], r['candidate_id']): r for r in
                          read(ROOT/'update015-current-all-matrix.json')['results']}
    index_rows = {(r['case_id'], r['candidate_id']): r for r in
                  read(ROOT/'update015-current-candidate-index.json')['results']}
    assert set(offline_rows) == set(compatibility_rows) and len(offline_rows) == 8
    assert set(index_rows) == set(offline_rows)
    draft = copy.deepcopy(source)
    acceptance = read(ROOT/'delivery-acceptance-contracts.json')
    assert acceptance['assignment_id'] == ROOT.name
    assert set(acceptance['contracts']) == {entry['case_id'] for entry in draft['cases']}
    draft['format'] = 'worker-execution-manifest'
    draft['status'] = 'partial_cpu_candidate_proofs_bound_original_unverified'
    draft['native_handoff_scope'] = 'env_only_no_original_claim'
    law = read(ROOT/'case-plan.json')
    for entry in draft['cases']:
        case_id = entry['case_id']
        entry['delivery_acceptance'] = copy.deepcopy(acceptance['contracts'][case_id])
        validate_case(ROOT, entry, ['full-train'])
        short = case_id.rsplit('__', 1)[-1]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        candidates = [{'id': 'primary', 'construction_sha256': entry['construction_sha256']}]
        candidates += entry['candidates']
        for candidate in candidates:
            ident = candidate['id']
            key = (case_id, ident)
            row = offline_rows.pop(key)
            comp_row = compatibility_rows.pop(key)
            indexed = index_rows.pop(key)
            construction_sha = candidate['construction_sha256']
            assert row['construction_sha256'] == construction_sha
            assert comp_row['construction_sha256'] == construction_sha
            assert row['offline_passed'] and comp_row['compatibility_passed']
            log = ROOT/row['log']
            assert sha(log) == row['log_sha256']
            assert row['manifest_sha256'] == indexed['manifest_sha256']
            assert sha(ROOT/indexed['manifest']) == indexed['manifest_sha256']
            output = Path(row['output']).resolve()
            assert REPO/'.runtime-work' in output.parents
            assert sha(output/'construction.json') == construction_sha
            assert sha(output/'offline.log') == row['runtime_log_sha256']
            command = row['command']
            assert case_id in command and ident in command and indexed['manifest'] in command
            archived = ROOT/'canonical-proof-bindings'/short/ident
            archived.mkdir(parents=True, exist_ok=True)
            offline_log = archived/'offline.log'
            shutil.copyfile(log, offline_log)
            candidate['offline'] = {
                'exit_code': 0, 'construction_sha256': construction_sha,
                'command': command,
                'log': str(offline_log.relative_to(ROOT)),
                'log_sha256': sha(offline_log)}
            sub = Path('update015-current-all')/short/ident
            receipt = ROOT/sub/'compatibility.json'
            result = read(receipt)
            assert result['passed'] and result['construction_sha256'] == construction_sha
            assert result['case_id'] == case_id and result['candidate_id'] == ident
            assert sha(ROOT/sub/'current-command.log') == comp_row['compatibility_sha256']
            assert sha(ROOT/sub/'saved-analysis.log') == result['log_sha256']
            assert sha(ROOT/sub/'negative-analysis.log') == result['negative_log_sha256']
            for name in ('compatibility.json','saved-analysis.log','negative-analysis.log'):
                shutil.copyfile(ROOT/sub/name, archived/name)
            candidate['compatibility'] = {
                'receipt': str((archived/'compatibility.json').relative_to(ROOT)),
                'sha256': sha(archived/'compatibility.json'),
                'log': str((archived/'saved-analysis.log').relative_to(ROOT)),
                'negative_log': str((archived/'negative-analysis.log').relative_to(ROOT))}
        entry['offline'] = candidates[0]['offline']
        entry['compatibility'] = candidates[0]['compatibility']
        entry['negative'] = {'log': candidates[0]['compatibility']['negative_log']}
        entry['acquisition'] = {name: {
            'entrypoint': 'finalize_current.py',
            'method': 'derive '+name+' from retained Native actor/frame rows',
            'evidence': 'native-raw-actors.jsonl and video_frames.jsonl'}
            for name in ('ego_pose', 'ego_speed', 'ego_lane_id', 'ego_road_id',
                         'path_length_m', 'right_lane_exit')}
        validate(ROOT, entry, law['law_id'], law['cell_id'], required=True,
                 require_alternate=True, candidate_count=4)
    assert not offline_rows and not compatibility_rows and not index_rows
    target = ROOT/'canonical-execution-draft.json'
    target.write_text(json.dumps(draft, indent=2)+'\n')
    print(json.dumps({'draft': str(target.relative_to(REPO)),
                      'sha256': sha(target), 'cases': len(draft['cases']),
                      'candidate_proofs_bound': 8, 'original_native_observed': False}))


if __name__ == '__main__':
    main()
