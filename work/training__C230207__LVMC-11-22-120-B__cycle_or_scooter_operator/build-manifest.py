"""Bind exact signed-bicycle constructions and their CPU proof receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return str(path.relative_to(HERE))


def compatibility(case_dir, candidate):
    prefix = 'primary' if candidate == 'primary' else 'fallback1'
    receipt = case_dir / (prefix + '-compatibility.json')
    return {'receipt': ref(receipt), 'sha256': sha(receipt),
            'log': ref(case_dir / (prefix + '-compatibility-analysis.log')),
            'negative_log': ref(case_dir / (prefix + '-negative-analysis.log'))}


def offline(entry, suffix, candidate):
    name = (f'proof-offline-{suffix}-current.log' if candidate == 'primary'
            else f'proof-offline-{suffix}-fallback1.log')
    log = HERE / name
    construction_hash = (entry['construction_sha256'] if candidate == 'primary'
                         else entry['candidates'][0]['construction_sha256'])
    return {'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{AID}/selected-offline-manifest.json --case {entry["case_id"]} --candidate {candidate} --output .runtime-work/c230207-offline-{suffix}-{candidate}',
            'construction_sha256': construction_hash, 'exit_code': 0,
            'log': name, 'log_sha256': sha(log)}


def main():
    manifest = json.loads((HERE / 'selected-offline-manifest.json').read_text())
    manifest['format'] = 'worker-execution-manifest'
    manifest['status'] = 'delivery_prepared'
    manifest['delivery_ready'] = True
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        case_dir = HERE / 'cases' / suffix
        primary = HERE / entry['construction']
        entry['construction_sha256'] = sha(primary)
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        proof = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': ref(proof), 'sha256': sha(proof)}
        entry['offline'] = offline(entry, suffix, 'primary')
        entry['compatibility'] = compatibility(case_dir, 'primary')
        entry['negative'] = {'log': ref(case_dir / 'primary-negative-analysis.log')}
        for candidate in entry['candidates']:
            candidate['construction_sha256'] = sha(HERE / candidate['construction'])
            candidate['offline'] = offline(entry, suffix, candidate['id'])
            candidate['compatibility'] = compatibility(case_dir, candidate['id'])
        entry['acquisition'] = {
            'dev.regulatory_sign': {'entrypoint': 'finalize.py', 'method': 'Original sign and face source review joined to Native readback', 'evidence': 'restriction-context.json,road.xodr,original-source-review.json'},
            'dev.governs': {'entrypoint': 'finalize.py', 'method': 'Original sign orientation and governed road/survey join', 'evidence': 'restriction-context.json,road.xodr'},
            'ru.bicycle': {'entrypoint': 'finalize.py', 'method': 'Original bicycle blueprint and wheel/subtype review', 'evidence': 'bicycle-poses.jsonl,restriction-context.json,original-source-review.json'},
            'st.roadway': {'entrypoint': 'finalize.py', 'method': 'Native surveyed roadway lane and rider footprint join', 'evidence': 'road.xodr,restriction-context.json,bicycle-poses.jsonl'},
            'rel.occupies': {'entrypoint': 'finalize.py', 'method': 'Original frame-joined bicycle position and signed road polygon', 'evidence': 'bicycle-poses.jsonl,video_frames.jsonl,restriction-context.json'},
        }
        audit = HERE / 'native/delivery_audit.py'
        positive = case_dir / 'delivery-positive.log'
        negative = case_dir / 'delivery-negative.log'
        base = f'.venv-cpu/bin/python -B work/{AID}/native/delivery_audit.py --case {case}'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': ref(audit), 'script_sha256': sha(audit),
            'command': base + ' --selftest', 'test_exit_code': 0,
            'test_log': ref(positive), 'test_log_sha256': sha(positive),
            'negative_command': base + ' --negative-selftest', 'negative_exit_code': 1,
            'negative_expected_error': 'Missing delivery source: bicycle-poses.jsonl',
            'negative_log': ref(negative), 'negative_log_sha256': sha(negative),
            'scope': 'Synthetic CPU audit mechanics; original designation, sign pixels, bicycle subtype and physical completion remain source-gated',
        }
        saved = case_dir / 'process-saved.log'
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$ADAPTER_CHECK" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'feedback_command': 'cat "$SAVED_VERSION/processing.json"',
            'test_command': f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{AID}/draft-signed-roadway-manifest.json --case {case} --attempt .runtime-work/c230207-compat-{suffix}-v3 --output .runtime-work/c230207-saved-{suffix} --library runtime/library --validator "$ADAPTER_CHECK"',
            'test_exit_code': 0, 'test_log': ref(saved),
            'test_log_sha256': sha(saved),
            'test_receipt': ref(case_dir / 'process-saved.json'),
            'test_receipt_sha256': sha(case_dir / 'process-saved.json'),
        }
    target = HERE / 'execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    primary = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    (HERE / 'construction.json').write_text(json.dumps(primary, indent=2) + '\n')
    for item in primary['files']:
        path = HERE / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    print(json.dumps({'manifest_sha256': sha(target),
                      'case_ids': [entry['case_id'] for entry in manifest['cases']]}))


if __name__ == '__main__':
    main()
