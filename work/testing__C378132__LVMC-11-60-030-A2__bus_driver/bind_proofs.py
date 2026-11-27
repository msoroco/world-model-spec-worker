"""Bind exact A2 CPU proof outputs to source-hashed delivery manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / '.runtime-work/c378132-a2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def cleaned(source, destination):
    content = source.read_text()
    destination.write_text(content.rstrip() + '\n' if content else '')
    return sha(destination)


def bind():
    draft = ROOT / 'execution-manifest.draft.json'
    manifest = json.loads(draft.read_text())
    manifest['format'] = 'worker-execution-manifest'
    manifest['status'] = 'draft_delivery_prepared'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.split('__')[-1]
        folder = ROOT / 'cases' / suffix
        compat = SCRATCH / ('compat-' + suffix + ('-v4' if suffix == 'outside_tour_bus' else '-v3'))
        proof = json.loads((compat / 'compatibility.json').read_text())
        if proof['construction_sha256'] != entry['construction_sha256'] or not proof['passed']:
            raise ValueError('changed exact compatibility proof: ' + suffix)
        receipt = folder / 'primary-compatibility.json'
        analysis = folder / 'primary-compat-analysis.log'
        negative = folder / 'primary-compat-negative.log'
        cleaned(compat / 'compatibility-analysis.log', analysis)
        if proof['log_sha256'] != sha(analysis):
            raise ValueError('compatibility analysis log changed by cleanup')
        cleaned(compat / 'negative-analysis.log', negative)
        if proof['negative_log_sha256'] != sha(negative):
            raise ValueError('compatibility negative log changed by cleanup')
        write(receipt, proof)
        entry['compatibility'] = {'receipt': str(receipt.relative_to(ROOT)),
                                  'sha256': sha(receipt), 'log': str(analysis.relative_to(ROOT))}
        entry['negative'] = {'log': str(negative.relative_to(ROOT))}
        log = folder / 'offline.log'
        cleaned(SCRATCH / ('offline-' + suffix + '-v3') / 'offline.log', log)
        offline_command = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline --manifest '
            + str(draft.relative_to(REPO)) + ' --case ' + case_id + ' --output .runtime-work/c378132-a2/offline-'
            + suffix + '-v3 --python "$PWD/.venv-cpu/bin/python"')
        entry['offline'] = {'command': offline_command, 'exit_code': 0,
                            'construction_sha256': entry['construction_sha256'],
                            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)}
        entry['acquisition'] = {
            'original_bus_stop_history': {'entrypoint': 'bus_location.py', 'method': 'source-hashed independent stopped-interval review joined to 900 Native frames', 'evidence': 'activity.json, native.json'},
            'designated_location_and_route': {'entrypoint': 'bus_location.py', 'method': 'actual City Traffic Engineer five-place designation and assigned route', 'evidence': 'designation.json, site.json, route.json'},
            'passenger_baggage_purpose': {'entrypoint': 'assemble_reviewed_activity.py', 'method': 'independent passenger, baggage or cargo-only purpose review', 'evidence': 'purpose.json, activity.json'},
            'exception_and_bus_class': {'entrypoint': 'assemble_reviewed_activity.py', 'method': 'independent tour-bus classification and emergency circumstance review', 'evidence': 'identity.json, circumstances.json'},
            'four_camera_frame_identity': {'entrypoint': 'native_capture.py', 'method': 'same Native world tick for all four RGB cameras at 20 Hz', 'evidence': 'native.json, four Matroska streams, video_frames.jsonl'}}
        acceptance = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'independent/delivery_audit.py', 'script_sha256': sha(ROOT/'independent/delivery_audit.py'),
            'command': 'PYTHONDWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ROOT.name + '/independent/prove_delivery_audit.py ' + case_id,
            'negative_command': 'PYTHONDWRITEBYTECODE=1 .venv-cpu/bin/python work/' + ROOT.name + '/independent/prove_delivery_audit.py ' + case_id + ' --negative',
            'test_exit_code': 0, 'test_log': str((folder/'delivery-positive.log').relative_to(ROOT)),
            'test_log_sha256': sha(folder/'delivery-positive.log'),
            'negative_exit_code': 1, 'negative_expected_error': 'five permitted locations or assigned route unreviewed',
            'negative_log': str((folder/'delivery-negative.log').relative_to(ROOT)),
            'negative_log_sha256': sha(folder/'delivery-negative.log')}
        entry['delivery_acceptance'] = acceptance
        saved_command = ('PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved --manifest work/'
                         + ROOT.name + '/execution-manifest.json --case ' + case_id
                         + ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library "$LIBRARY" --validator "$VALIDATOR" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"')
        entry['post_capture'] = {'recorded_only': True, 'command': saved_command, 'feedback_command': saved_command}
    write(ROOT/'execution-manifest.json', manifest)
    print(f"bound {len(manifest['cases'])} exact A2 compatibility/offline/physical/delivery proof contracts")


if __name__ == '__main__':
    bind()
