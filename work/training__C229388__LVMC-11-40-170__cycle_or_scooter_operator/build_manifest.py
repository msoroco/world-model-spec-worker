"""Bind stable selected-case CPU receipts to the LVMC parking handoff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SHA = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'compat-draft-manifest.json').read_text())
    manifest['status'] = 'delivery_prepared'
    manifest['delivery_ready'] = True
    for entry in manifest['cases']:
        cid = entry['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        case_dir = HERE / 'cases' / suffix
        primary = HERE / entry['construction']
        entry['construction_sha256'] = SHA(primary)
        proof_path = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {
            'receipt': str(proof_path.relative_to(HERE)), 'sha256': SHA(proof_path)}
        entry['offline'] = offline(cid, suffix, 'primary', entry['construction_sha256'])
        for candidate in entry['candidates']:
            candidate['construction_sha256'] = SHA(HERE / candidate['construction'])
            candidate['offline'] = offline(cid, suffix, candidate['id'], candidate['construction_sha256'])
            candidate['compatibility'] = compatibility(case_dir, suffix, candidate['id'])
        entry['compatibility'] = compatibility(case_dir, suffix, 'primary')
        entry['negative'] = {'log': str((case_dir / 'primary-negative-analysis.log').relative_to(HERE))}
        entry['acquisition'] = {
            name: {'entrypoint': 'measure_parking.py',
                'method': 'Native parked-device footprint and source-reviewed rack, sidewalk, curb and pedestrian corridor join',
                'evidence': 'parking_context.json,native_parking_trace.jsonl'}
            for name in ('ru.bicycle', 'ru.electric_bicycle', 'ru.electric_scooter',
                'drv.standing_or_parked', 'st.roadway', 'st.road_edge', 'st.sidewalk',
                'rel.occupies', 'ru.pedestrian', 'rel.surface_gap', 'st.obstruction')}
        entry['delivery_acceptance'] = delivery(cid, suffix)
        receipt = case_dir / 'process-saved.json'
        receipt.write_bytes((HERE / f'saved-{suffix}.log').read_bytes())
        attempt = '.runtime-work/c229388-compat-probe_01-primary-v2' if suffix == 'probe_01' else '.runtime-work/c229388-compat-probe_02-primary'
        saved = '.runtime-work/c229388-saved-probe_01' if suffix == 'probe_01' else '.runtime-work/c229388-saved-probe_02'
        entry['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {cid} --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library --validator "$ADAPTER_CHECK" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
            'feedback_command': 'cat "$SAVED_VERSION/processing.json"',
            'test_command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/compat-draft-manifest.json --case {cid} --attempt {attempt} --output {saved} --library runtime/library --validator "$ADAPTER_CHECK"',
            'test_exit_code': 0,
            'test_log': f'saved-{suffix}.log',
            'test_log_sha256': SHA(HERE / f'saved-{suffix}.log'),
            'test_receipt': str(receipt.relative_to(HERE)),
            'test_receipt_sha256': SHA(receipt),
        }
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def offline(cid, suffix, candidate, construction_hash):
    log = HERE / f'proof-offline-{suffix}-{candidate}.log'
    return {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/selected-offline-manifest.json --case {cid} --candidate {candidate} --output .runtime-work/c229388-offline-final-{suffix}-{candidate}',
            'construction_sha256': construction_hash, 'exit_code': 0,
            'log': log.name, 'log_sha256': SHA(log)}


def compatibility(case_dir, suffix, candidate):
    prefix = 'primary' if candidate == 'primary' else 'fallback1'
    receipt = case_dir / f'{prefix}-compatibility.json'
    return {'receipt': str(receipt.relative_to(HERE)), 'sha256': SHA(receipt),
            'log': str((case_dir / f'{prefix}-compatibility-analysis.log').relative_to(HERE)),
            'negative_log': str((case_dir / f'{prefix}-negative-analysis.log').relative_to(HERE))}


def delivery(cid, suffix):
    script = HERE / 'native/delivery_audit.py'
    positive = HERE / f'delivery-{suffix}-selftest.log'
    negative = HERE / f'delivery-{suffix}-negative-selftest.log'
    base = f'.venv-cpu/bin/python work/{AID}/native/delivery_audit.py --case {cid}'
    return {'case_id': cid, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'native/delivery_audit.py', 'script_sha256': SHA(script),
            'command': base + ' --selftest', 'test_exit_code': 0,
            'test_log': positive.name, 'test_log_sha256': SHA(positive),
            'negative_command': base + ' --negative-selftest', 'negative_exit_code': 1,
            'negative_expected_error': 'Missing delivery source: native_parking_trace.jsonl',
            'negative_log': negative.name, 'negative_log_sha256': SHA(negative),
            'scope': 'Synthetic CPU audit mechanics; original Native rack, pedestrian and operator review remains source-gated'}


if __name__ == '__main__':
    main()
