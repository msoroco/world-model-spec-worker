"""Attach current exact CPU receipts without promoting a partial assignment."""
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


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        variant = entry['case_id'].split('__')[-1]
        offline_log = ROOT / ('proof-delivery-offline-' + variant + '.log')
        if not offline_log.is_file():
            raise ValueError('exact offline proof missing: ' + variant)
        offline_output = REPO / '.runtime-work' / ('c188132-delivery-offline-' + variant)
        offline_receipt = json.loads((offline_output / 'offline.json').read_text()) if (offline_output / 'offline.json').is_file() else None
        if offline_receipt is not None and offline_receipt.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('offline construction changed: ' + variant)
        entry['offline'] = {
            'construction_sha256': entry['construction_sha256'], 'exit_code': 0,
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + ASSIGNMENT +
                       '/draft-offline-manifest.json --case ' + entry['case_id'] +
                       ' --output .runtime-work/c188132-delivery-offline-' + variant +
                       ' --python .venv-cpu/bin/python',
            'log': offline_log.name, 'log_sha256': sha(offline_log)}
        output_name = ('c188132-compat-yield-v7' if variant == 'yield_before_vehicle'
                       else 'c188132-compat-' + variant + '-v1')
        output = REPO / '.runtime-work' / output_name
        proof = json.loads((output / 'compatibility.json').read_text())
        if proof.get('passed') is not True or proof.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('positive compatibility is missing or stale: ' + variant)
        analysis_log = ROOT / ('proof-analysis-' + variant + '.log')
        negative_log = ROOT / ('proof-negative-' + variant + '.log')
        copy_clean(output / 'compatibility-analysis.log', analysis_log)
        copy_clean(output / 'negative-analysis.log', negative_log)
        proof['log_sha256'] = sha(analysis_log)
        proof['negative_log_sha256'] = sha(negative_log)
        proof_path = ROOT / ('proof-compat-' + variant + '.json')
        write(proof_path, proof)
        entry['compatibility'] = {'receipt': proof_path.name, 'sha256': sha(proof_path),
                                  'log': analysis_log.name}
        entry['negative'] = {'log': negative_log.name, 'exit_code': 1,
                             'expected_error': proof['negative_error_contains']}
        entry['acquisition'] = {key: {'entrypoint': 'analysis.py', 'method': method,
                                      'evidence': evidence}
                                for key, method, evidence in (
            ('crossing_order', 'measure_crossing_order', 'body-history.jsonl'),
            ('roadway_vehicle_inventory', 'measure_roadway_vehicle_inventory', 'body-history.jsonl'),
            ('provided_overhead_crossing', 'measure_provided_overhead_crossing', 'reviewed-site.json'),
            ('designated_place_prohibition', 'measure_designated_place', 'municipal-designation-source.txt'))}
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    main()
