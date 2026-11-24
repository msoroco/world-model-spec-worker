"""Independently verify eight current synthetic CPU chains and source isolation."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c10316-head-refresh-v5'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    proof = read(HERE / 'head-refresh/proof.json')
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = read(manifest_path)
    if proof['manifest_sha256'] != sha(manifest_path) or len(proof['records']) != 8:
        raise ValueError('Current source-bound eight-chain proof missing')
    by_case = {entry['case_id']: entry for entry in manifest['cases']}
    seen = set()
    for record in proof['records']:
        key = (record['case_id'], record['candidate'])
        if key in seen:
            raise ValueError('Duplicate candidate proof')
        seen.add(key)
        entry = by_case[record['case_id']]
        selected = entry if record['candidate'] == 'primary' else next(
            item for item in entry['candidates'] if item['id'] == record['candidate'])
        if sha(HERE / selected['construction']) != selected['construction_sha256'] or \
                record['construction_sha256'] != selected['construction_sha256']:
            raise ValueError('Candidate construction source differs')
        folder = SCRATCH / (record['case_id'].rsplit('__', 1)[-1] + '-' + record['candidate'])
        attempt = folder / 'compat'
        saved = folder / 'saved/v0001/processing.json'
        c = read(attempt / 'compatibility.json')
        s = read(saved)
        analysis = read(attempt / 'analysis-report.json')
        if any((
            sha(attempt / 'compatibility.json') != record['compatibility_receipt_sha256'],
            sha(saved) != record['saved_receipt_sha256'],
            sha(attempt / 'negative-analysis.log') != record['negative_log_sha256'],
            sha(HERE / record['compatibility_log']) != record['compatibility_log_sha256'],
            sha(HERE / record['saved_log']) != record['saved_log_sha256'],
            c['fixture_recipe_sha256'] != sha(ROOT / entry['fixture_recipe']),
            c['construction_sha256'] != selected['construction_sha256'],
            c['negative_removed'] != 'no-countdown-samples.jsonl',
            not c['passed'], not s['passed'], not s['recorded_only'],
            s['timestamp_joins']['frames'] != 600,
            s['final_video_checks']['frames'] != 600,
            s['physical_acceptance_claimed'] is not False,
        )):
            raise ValueError('Public or saved source receipt differs: ' + str(key))
        if c['negative_error_contains'] not in (attempt / 'negative-analysis.log').read_text():
            raise ValueError('Missing-source rejection absent')
        values = analysis['measurements']
        if set(values) != {'no_countdown_entry_and_clearance', 'cited_exception_context'}:
            raise ValueError('Selected requirements missing source measurements')
        expected = 'walk' if key[0].endswith('controlled_1') else 'dont_walk_flashing'
        observed = values['no_countdown_entry_and_clearance']['value']
        if observed['entry_indication'] != expected or observed['original_frames'] != 600 or \
                observed['source_kind'] != 'synthetic_scene_request' or \
                observed['governing_device_observed'] is not False:
            raise ValueError('Synthetic comparison measurement differs')
        if values['cited_exception_context']['value']['source_kind'] != 'synthetic_scene_request':
            raise ValueError('Exception context misstates provenance')
    expected = {(case_id, candidate) for case_id in by_case for candidate in
                ('primary', 'fallback1', 'fallback2', 'fallback3')}
    if seen != expected:
        raise ValueError('Selected candidate matrix incomplete')
    receipt = {'format': 'c10316-head-refresh-independent-source-audit',
               'passed': True, 'chains': 8, 'manifest_sha256': sha(manifest_path),
               'proof_sha256': sha(HERE / 'head-refresh/proof.json'),
               'physical_or_legal_acceptance_claimed': False}
    path = HERE / 'head-refresh/audit.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()
