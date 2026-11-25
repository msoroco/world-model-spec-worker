"""Attach exact primary and fallback CPU receipts, keeping status partial."""
from __future__ import annotations

import json
from pathlib import Path
from overpass_source import sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def copy_clean(source, destination):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    destination.write_text('\n'.join(lines) + '\n')


def attach(entry, variant, candidate_id):
    selected = entry if candidate_id == 'primary' else next(
        c for c in entry['candidates'] if c['id'] == candidate_id)
    offline_log = ROOT / ('proof-final-offline-' + variant + '-' + candidate_id + '.log')
    if not offline_log.is_file():
        raise ValueError('exact offline proof missing: ' + variant + ' ' + candidate_id)
    offline = json.loads(offline_log.read_text())
    if offline.get('offline_passed') is not True or offline.get('case_id') != entry['case_id'] or offline.get('candidate_id') != candidate_id:
        raise ValueError('exact offline proof differs: ' + variant + ' ' + candidate_id)
    selected['offline'] = {
        'construction_sha256': selected['construction_sha256'], 'exit_code': 0,
        'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ASSIGNMENT +
                   '/execution-manifest.json --case ' + entry['case_id'] +
                   ' --candidate ' + candidate_id +
                   ' --output .runtime-work/c188132-nov25c-offline-' + variant + '-' + candidate_id +
                   ' --python .venv-cpu/bin/python',
        'log': offline_log.name, 'log_sha256': sha(offline_log)}
    output = REPO / '.runtime-work' / ('c188132-nov25c-compat-' + variant + '-' + candidate_id)
    proof = json.loads((output / 'compatibility.json').read_text())
    if (proof.get('passed') is not True or proof.get('case_id') != entry['case_id'] or
            proof.get('candidate_id') != candidate_id or
            proof.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('positive compatibility is missing or stale: ' + variant + ' ' + candidate_id)
    suffix = variant + '-' + candidate_id
    analysis_log = ROOT / ('proof-analysis-' + suffix + '.log')
    negative_log = ROOT / ('proof-negative-' + suffix + '.log')
    copy_clean(output / 'compatibility-analysis.log', analysis_log)
    copy_clean(output / 'negative-analysis.log', negative_log)
    proof['log_sha256'] = sha(analysis_log)
    proof['negative_log_sha256'] = sha(negative_log)
    proof_path = ROOT / ('proof-compat-' + suffix + '.json')
    write(proof_path, proof)
    selected['compatibility'] = {'receipt': proof_path.name, 'sha256': sha(proof_path),
                                  'log': analysis_log.name, 'negative_log': negative_log.name}
    if candidate_id == 'primary':
        entry['negative'] = {'log': negative_log.name, 'exit_code': 1,
                             'expected_error': proof['negative_error_contains']}
        entry['acquisition'] = {key: {'entrypoint': 'analysis.py', 'method': method,
                                      'evidence': evidence}
                                for key, method, evidence in (
            ('crossing_order', 'measure_crossing_order', 'body-history.jsonl'),
            ('roadway_vehicle_inventory', 'measure_roadway_vehicle_inventory', 'body-history.jsonl'),
            ('provided_overhead_crossing', 'measure_provided_overhead_crossing', 'reviewed-site.json'),
            ('designated_place_prohibition', 'measure_designated_place', 'municipal-designation-source.txt'))}


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        variant = entry['case_id'].split('__')[-1]
        for candidate_id in ('primary', 'fallback1'):
            attach(entry, variant, candidate_id)
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
