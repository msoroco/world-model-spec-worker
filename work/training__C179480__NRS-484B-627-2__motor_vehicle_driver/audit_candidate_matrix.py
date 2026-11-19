"""Independently bind the combined draft matrix's CPU diagnostic receipts."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSETS = ROOT / '.runtime-work/c179480-update092-matrix'
MANIFEST = HERE / 'candidate-matrix-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(MANIFEST)
    manifest_sha = sha(MANIFEST)
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.rsplit('__', 1)[-1]
        choices = [{'id': 'primary', 'construction_sha256': entry['construction_sha256']}, *entry['candidates']]
        for choice in choices:
            candidate = choice['id']
            stem = f'update092-{name}-{candidate}'
            compat = ASSETS / f'{name}-{candidate}-compatibility'
            saved = ASSETS / f'{name}-{candidate}-saved/v0001'
            artifacts = {
                'selection': compat / 'candidate-selection.json',
                'compatibility': compat / 'compatibility.json',
                'analysis_log': compat / 'compatibility-analysis.log',
                'negative_log': compat / 'negative-analysis.log',
                'processing': saved / 'processing.json',
            }
            selection = read(artifacts['selection'])
            receipt = read(artifacts['compatibility'])
            processing = read(artifacts['processing'])
            identity = {'case_id': case, 'candidate_id': candidate,
                        'construction_sha256': choice['construction_sha256']}
            if any(selection.get(k) != v or receipt.get(k) != v for k, v in identity.items()):
                raise ValueError(f'Candidate or compatibility identity mismatch: {stem}')
            if selection['manifest_sha256'] != manifest_sha:
                raise ValueError(f'Compatibility selected another manifest: {stem}')
            if receipt.get('passed') is not True or not {'selected_measurements', 'negative_case_source', 'lean_decoder', 'final_decode'} <= set(receipt.get('checks', [])):
                raise ValueError(f'Incomplete compatibility: {stem}')
            if sha(artifacts['analysis_log']) != receipt['log_sha256'] or sha(artifacts['negative_log']) != receipt['negative_log_sha256']:
                raise ValueError(f'Compatibility logs changed: {stem}')
            if receipt['negative_error_contains'] not in artifacts['negative_log'].read_text():
                raise ValueError(f'Missing-source rejection absent: {stem}')
            if any(processing.get(k) != v for k, v in {'case_id': case, 'candidate_id': candidate,
                    'passed': True, 'recorded_only': True, 'originals_preserved': True,
                    'missing_evidence': False, 'physical_acceptance_claimed': False,
                    'legal_acceptance_claimed': False}.items()):
                raise ValueError(f'Saved-processing evidence incomplete: {stem}')
            if processing['analysis_revision']['construction_sha256'] != choice['construction_sha256']:
                raise ValueError(f'Saved analysis selected another construction: {stem}')
            if (processing.get('timestamp_joins', {}).get('frames') != 600
                    or processing.get('timestamp_joins', {}).get('passed') is not True
                    or processing.get('final_video_checks', {}).get('frames') != 600
                    or processing.get('final_video_checks', {}).get('passed') is not True):
                raise ValueError(f'Saved timing or video incomplete: {stem}')
            copied = {}
            for kind, source in artifacts.items():
                destination = HERE / f'{stem}-{kind}.json' if kind in ('selection', 'compatibility', 'processing') else HERE / f'{stem}-{kind}.log'
                shutil.copyfile(source, destination)
                copied[kind] = {'path': destination.name, 'sha256': sha(destination)}
            for phase in ('offline', 'compatibility', 'saved'):
                log = HERE / f'{stem}-{phase}.log'
                if not log.is_file():
                    raise ValueError(f'Missing exact command log: {log.name}')
                copied[f'{phase}_command_log'] = {'path': log.name, 'sha256': sha(log)}
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': choice['construction_sha256'], 'artifacts': copied})
    result = {'format': 'worker-candidate-matrix-diagnostic-audit',
              'scope': 'synthetic CPU software diagnostics only',
              'manifest': MANIFEST.name, 'manifest_sha256': manifest_sha,
              'passed': True, 'case_count': 4, 'candidate_count': len(rows),
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
              'rows': rows}
    target = HERE / 'update092-candidate-matrix-audit.json'
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return target


if __name__ == '__main__':
    print(audit())
