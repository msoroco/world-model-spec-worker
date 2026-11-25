"""Bind current runtime CPU proofs for the two selected crossing cases."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    target = HERE / 'execution-manifest.json'
    manifest = json.loads(target.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(BASE + '__')
        label = 'marked' if suffix == 'marked_crosswalk' else 'unmarked'
        physical = HERE / 'physical' / suffix / 'physical-proof.json'
        if json.loads(physical.read_text())['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical proof binds another construction')
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)), 'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        source_map = {
            'ru.subject': 'pedestrian-original.jsonl',
            'ru.pedestrian': 'pedestrian-original.jsonl',
            'st.intersection': 'native-survey.json, native-survey-media/map.txt',
            'st.lane_enters': 'pedestrian-original.jsonl, native-survey.json',
            'dev.traffic_signal': 'controls-original.jsonl, native-survey-media/control-1.txt, native-survey-media/control-2.txt',
            'st.crosswalk': 'native-survey.json, native-survey-media/marking.txt, pedestrian-original.jsonl',
            'rel.occupies': 'pedestrian-original.jsonl, native-survey.json',
            'st.roadway': 'native-survey.json, pedestrian-original.jsonl',
            'kin.position': 'pedestrian-original.jsonl, video_frames.jsonl',
        }
        entry['acquisition'] = {
            atom: {'entrypoint': 'runner.py', 'method': 'original Native survey, actor readback and synchronized source hash', 'evidence': evidence}
            for atom, evidence in source_map.items()
        }
        saved_source = ROOT / '.runtime-work' / f'c109166-287-1c-saved-{label}-primary-v5'
        saved_log = HERE / f'saved-{label}-primary.log'
        shutil.copyfile(ROOT / '.runtime-work' / f'c109166-287-1c-saved-{label}-primary-v5.log', saved_log)
        saved_receipt = HERE / 'cases' / suffix / 'primary' / 'saved-processing.json'
        shutil.copyfile(saved_source / 'v0001' / 'processing.json', saved_receipt)
        if (json.loads(saved_receipt.read_text()).get('recorded_only') is not True or
                json.loads(saved_receipt.read_text()).get('passed') is not True):
            raise ValueError('Saved-only diagnostic processing failed')
        script = HERE / 'delivery_audit.py'
        positive = HERE / f'delivery-{label}-positive.log'
        negative = HERE / f'delivery-{label}-negative.log'
        if ('"passed": true' not in positive.read_text() or
                'Missing required source: controls-original.jsonl' not in negative.read_text()):
            raise ValueError('Independent delivery positive/negative proof failed')
        prefix = f'.venv-cpu/bin/python work/{BASE}/delivery_audit.py --case {case_id} --candidate primary'
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion', 'source_bound_exception_review'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': prefix + f' --attempt .runtime-work/c109166-287-1c-public-{label}-primary-v3 --processing .runtime-work/c109166-287-1c-saved-{label}-primary-v5/v0001/processing.json --output .runtime-work/c109166-287-1c-delivery-{label}-positive-v5.json --diagnostic',
            'test_exit_code': 0, 'test_log': positive.name, 'test_log_sha256': sha(positive),
            'negative_command': prefix + f' --attempt .runtime-work/c109166-287-1c-public-{label}-primary-v3 --processing .runtime-work/c109166-287-1c-negative-processing-{label}-v5.json --output .runtime-work/c109166-287-1c-delivery-{label}-negative-v5.json --diagnostic',
            'negative_exit_code': 1, 'negative_expected_error': 'Missing required source: controls-original.jsonl',
            'negative_log': negative.name, 'negative_log_sha256': sha(negative)}
        entry['post_capture'] = {
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE}/execution-manifest.json --case {case_id} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$ADAPTER_CHECK"',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': saved_log.name, 'test_log_sha256': sha(saved_log)}
        for candidate_id in ('primary', 'fallback1'):
            selected = entry if candidate_id == 'primary' else entry['candidates'][0]
            tag = label + '-' + candidate_id
            destination = HERE / 'cases' / suffix / candidate_id
            offline_source = ROOT / '.runtime-work' / ('c109166-287-1c-offline-' + tag + '-v4') / 'offline.log'
            offline_log = destination / 'selected-offline.log'
            shutil.copyfile(offline_source, offline_log)
            if 'OK\n' not in offline_log.read_text():
                raise ValueError('Exact offline proof failed: ' + tag)
            selected['offline'] = {
                'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/execution-manifest.json --case {case_id} --candidate {candidate_id} --output .runtime-work/c109166-287-1c-offline-{tag}-v4',
                'log': str(offline_log.relative_to(HERE)), 'log_sha256': sha(offline_log)}
            source = ROOT / '.runtime-work' / ('c109166-287-1c-public-' + tag + '-v3')
            receipt = json.loads((source / 'compatibility.json').read_text())
            if (receipt.get('passed') is not True or receipt['case_id'] != case_id or
                    receipt['candidate_id'] != candidate_id or receipt['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Public compatibility proof failed or stale: ' + tag)
            analysis = destination / 'public-analysis.log'
            negative = destination / 'negative-analysis.log'
            shutil.copyfile(source / 'compatibility-analysis.log', analysis)
            shutil.copyfile(source / 'negative-analysis.log', negative)
            if sha(analysis) != receipt['log_sha256'] or sha(negative) != receipt['negative_log_sha256']:
                raise ValueError('Compatibility logs changed: ' + tag)
            receipt_path = destination / 'public-receipt.json'
            write(receipt_path, receipt)
            selected['compatibility'] = {'receipt': str(receipt_path.relative_to(HERE)),
                                         'sha256': sha(receipt_path),
                                         'log': str(analysis.relative_to(HERE)),
                                         'negative_log': str(negative.relative_to(HERE))}
            if candidate_id == 'primary':
                entry['negative'] = {'log': str(negative.relative_to(HERE)), 'log_sha256': sha(negative)}
    manifest['status'] = 'cpu_proofs_bound_source_review_pending'
    manifest['delivery_ready'] = False
    manifest['original_native_observed'] = False
    manifest['comparison_proof'] = {'path': 'comparison-proof.json',
                                    'sha256': sha(HERE / 'comparison-proof.json')}
    write(target, manifest)
    print(json.dumps({'bound_candidates': 4, 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
