"""Independently verify all six selected cases and 24 final-manifest CPU chains."""
import hashlib
import json
from pathlib import Path
import shlex

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def option(command, name):
    parts = shlex.split(command)
    require(name in parts and parts.index(name) + 1 < len(parts),
            'Proof command lacks ' + name)
    return parts[parts.index(name) + 1]


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    manifest_sha = sha(manifest_path)
    construction_matrix = read(HERE / 'update036-selected-construction-proof-matrix.json')
    process_matrix = read(HERE / 'update036-selected-process-saved-matrix.json')
    require(process_matrix['manifest_sha256'] == manifest_sha and
            process_matrix['status'] == 'complete_diagnostic',
            'Saved proof matrix does not bind final selected manifest')
    expected = {(case['case_id'], candidate)
                for case in manifest['cases']
                for candidate in ('primary', *(item['id'] for item in case['candidates']))}
    processes = {(row['case_id'], row['candidate_id']): row
                 for row in process_matrix['rows']}
    constructions = {(row['case_id'], row['candidate_id']): row
                     for row in construction_matrix['rows']}
    require(len(manifest['cases']) == 6 and len(expected) == 24 and
            set(processes) == set(constructions) == expected and
            len(process_matrix['rows']) == len(construction_matrix['rows']) == 24,
            'Final selected proof matrix lacks an exact candidate')
    checked = []
    for case in manifest['cases']:
        for candidate in ('primary', *(item['id'] for item in case['candidates'])):
            key = (case['case_id'], candidate)
            selected = case if candidate == 'primary' else next(
                item for item in case['candidates'] if item['id'] == candidate)
            construction = HERE / selected['construction']
            require(sha(construction) == selected['construction_sha256'],
                    'Selected construction changed')
            offline = selected['offline']
            require(offline['exit_code'] == 0 and
                    offline['construction_sha256'] == selected['construction_sha256'] and
                    sha(HERE / offline['log']) == offline['log_sha256'] and
                    '--case ' + case['case_id'] in offline['command'] and
                    '--candidate ' + candidate in offline['command'],
                    'Final selected offline proof differs')
            compatibility = selected['compatibility']
            compatible = read(HERE / compatibility['receipt'])
            require(sha(HERE / compatibility['receipt']) == compatibility['sha256'] and
                    compatible['passed'] is True and
                    compatible['case_id'] == case['case_id'] and
                    compatible['candidate_id'] == candidate and
                    compatible['construction_sha256'] == selected['construction_sha256'] and
                    sha(HERE / compatibility['log']) == compatible['log_sha256'] and
                    sha(HERE / compatibility['negative_log']) == compatible['negative_log_sha256'] and
                    {'selected_measurements', 'negative_case_source', 'lean_decoder',
                     'final_decode'} <= set(compatible['checks']),
                    'Final selected compatibility proof differs')
            row = processes[key]
            require(row['diagnostic_only'] is True and
                    sha(HERE / row['log']) == row['log_sha256'] and
                    option(row['command'], '--case') == case['case_id'] and
                    option(row['command'], '--manifest') == str(manifest_path),
                    'Final saved proof command or log differs')
            output = Path(option(row['command'], '--output'))
            receipt = output / 'v0001/processing.json'
            attempt = Path(option(row['command'], '--attempt'))
            processing = read(receipt)
            selection = read(attempt / 'candidate-selection.json')
            require(sha(receipt) == row['processing_receipt_sha256'] and
                    selection['manifest_sha256'] == manifest_sha and
                    selection['candidate_id'] == candidate and
                    selection['construction_sha256'] == selected['construction_sha256'] and
                    processing['passed'] is True and
                    processing['recorded_only'] is True and
                    processing['originals_preserved'] is True and
                    processing['case_id'] == case['case_id'] and
                    processing['candidate_id'] == candidate and
                    processing['analysis_revision']['construction_sha256'] ==
                    selected['construction_sha256'] and
                    processing['physical_acceptance_claimed'] is False and
                    processing['legal_acceptance_claimed'] is False and
                    processing['timestamp_joins']['frames'] == 480 and
                    processing['timestamp_joins']['passed'] is True,
                    'Final saved processing source chain differs')
            for source, digest in processing['original_source_hashes'].items():
                require(sha(attempt / source) == digest,
                        'Selected original source changed: ' + source)
            result_path = Path(processing['result'])
            result = read(result_path)
            require(sha(result_path) == processing['result_sha256'] and
                    result['case_id'] == case['case_id'] and
                    result['accepted'] is False and
                    result['legal_verdict_claimed'] is False,
                    'Selected diagnostic result changed or claimed original acceptance')
            checked.append({'case_id': case['case_id'], 'candidate_id': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'compatibility_sha256': compatibility['sha256'],
                            'processing_sha256': sha(receipt)})
    output = HERE / 'update036-final-selected-proof-audit.json'
    output.write_text(json.dumps({'format': 'c111256-final-selected-proof-audit-v1',
                                  'manifest_sha256': manifest_sha,
                                  'selected_cases': 6, 'candidate_bundles': 24,
                                  'rows': checked, 'passed': True,
                                  'original_recordings_accepted': 0}, indent=2) + '\n')
    print(json.dumps({'selected_cases': 6, 'candidate_bundles': 24,
                      'audit_sha256': sha(output),
                      'original_recordings_accepted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()
