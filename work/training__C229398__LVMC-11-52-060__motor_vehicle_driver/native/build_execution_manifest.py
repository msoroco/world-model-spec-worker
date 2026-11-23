"""Select the three source-reviewed boundary cases for CPU delivery preparation."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
ASSIGNMENT = PACKAGE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    draft = json.loads((PACKAGE / 'draft-primary-manifest.json').read_text())
    source = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    witnesses = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'witnesses.json').read_text())
    physical = json.loads((PACKAGE / 'diagnostic-fixture/physical-proof-index.json').read_text())
    semantic = json.loads((PACKAGE / 'proposals/semantic-index.json').read_text())
    assert len(witnesses) == 1 and witnesses[0]['witness']['audit_status'] == 'accepted'
    assert witnesses[0]['witness']['decision'] == 'conditional'
    assert source['local_snapshot']['memberships']['full-train'] == []
    assert semantic['assignment_id'] == ASSIGNMENT
    assert physical['manifest_sha256'] == sha(PACKAGE / 'draft-primary-manifest.json')
    assert len(draft['cases']) == len(physical['cases']) == 3
    cases = []
    for entry, preparation in zip(draft['cases'], physical['cases']):
        assert entry['case_id'] == preparation['case_id']
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        proof_dir = 'diagnostic-fixture/' + suffix + '/proofs/'
        positive = PACKAGE / (proof_dir + 'atoms-primary-positive.json')
        saved = PACKAGE / (proof_dir + 'atoms-primary-saved.json')
        analysis_log = PACKAGE / (proof_dir + 'atoms-primary-analysis.log')
        negative_log = PACKAGE / (proof_dir + 'atoms-primary-negative-analysis.log')
        assert json.loads(positive.read_text())['passed']
        assert json.loads(saved.read_text())['recorded_only']
        selected = dict(entry)
        selected['physical_preparation'] = {
            'receipt': preparation['receipt'], 'sha256': preparation['sha256']}
        selected['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                      'host_env_var': 'CARLA_HOST',
                                      'port_env_var': 'CARLA_PORT'}
        selected['compatibility'] = {
            'receipt': str(positive.relative_to(PACKAGE)), 'sha256': sha(positive),
            'log': str(analysis_log.relative_to(PACKAGE)),
            'negative_log': str(negative_log.relative_to(PACKAGE))}
        selected['negative'] = {'log': str(negative_log.relative_to(PACKAGE))}
        selected['saved_processing'] = {
            'receipt': str(saved.relative_to(PACKAGE)), 'sha256': sha(saved)}
        selected['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                       ASSIGNMENT + '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                       ' --library runtime/pipeline/library' +
                       ' --validator .runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': str(saved.relative_to(PACKAGE)),
            'test_log_sha256': sha(saved)}
        selected['acquisition'] = {
            'ru.vehicle': {'entrypoint': 'runner.py',
                           'method': 'retain Native vehicle and attachment actor inventory',
                           'evidence': 'native-raw-actors.jsonl, trace.jsonl'},
            'kin.extent': {'entrypoint': 'source_footprints.py',
                           'method': 'derive rotated vehicle, load and trailer vertices from retained poses and extents',
                           'evidence': 'native-raw-actors.jsonl, derived-source-footprints.jsonl'},
            'st.road_edge': {'entrypoint': 'runner.py',
                             'method': 'read back Native map curb candidate for independent review',
                             'evidence': 'road.xodr, native-curb-proposal.json, reviewed-curb.json'},
            'rel.occupies': {'entrypoint': 'projection_measure.py',
                             'method': 'measure full-part streetward distance perpendicular to reviewed curb',
                             'evidence': 'reviewed-curb.json, derived-source-footprints.jsonl'},
            'kin.position': {'entrypoint': 'runner.py',
                             'method': 'retain frame-joined Native actor poses',
                             'evidence': 'trace.jsonl, native-raw-actors.jsonl'},
            'maximum_projection_perpendicular_to_curb': {
                'entrypoint': 'projection_measure.py',
                'method': 'maximum of all 600 full-part curb-normal distances',
                'evidence': 'reviewed-curb.json, native-raw-actors.jsonl, derived-source-footprints.jsonl'}}
        selected['preparation_status'] = 'selected_cpu_proofs_current_physical_unverified'
        candidates = []
        for alternative in selected['candidates']:
            ident = alternative['id']
            receipt = PACKAGE / (proof_dir + 'atoms-' + ident + '-positive.json')
            positive_log = PACKAGE / (proof_dir + 'atoms-' + ident + '-analysis.log')
            negative = PACKAGE / (proof_dir + 'atoms-' + ident + '-negative-analysis.log')
            assert json.loads(receipt.read_text())['passed']
            alternative = dict(alternative)
            alternative['compatibility'] = {
                'receipt': str(receipt.relative_to(PACKAGE)), 'sha256': sha(receipt),
                'log': str(positive_log.relative_to(PACKAGE)),
                'negative_log': str(negative.relative_to(PACKAGE))}
            candidates.append(alternative)
        selected['candidates'] = candidates
        cases.append(selected)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'status': 'selected_cpu_draft',
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'source_branch': witnesses[0]['witness']['branch'],
                'cases': cases, 'original_native_observed': False,
                'delivery_ready': False}
    path = PACKAGE / 'execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'selected_cases': len(cases), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
