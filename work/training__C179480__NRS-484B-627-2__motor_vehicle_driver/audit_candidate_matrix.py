"""Independently bind the combined draft matrix's CPU diagnostic receipts."""
import hashlib
import json
import shutil
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'candidate-matrix-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(label):
    if label not in ('update092', 'update095', 'base-current'):
        raise ValueError('Unsupported diagnostic matrix label')
    assets = (ROOT / '.runtime-work/c179480-native-sweep' if label == 'base-current'
              else ROOT / '.runtime-work' / f'c179480-{label}-matrix')
    manifest = read(MANIFEST)
    manifest_sha = sha(MANIFEST)
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.rsplit('__', 1)[-1]
        choices = [{'id': 'primary', 'construction_sha256': entry['construction_sha256']}, *entry['candidates']]
        for choice in choices:
            candidate = choice['id']
            stem = f'{label}-{name}-{candidate}'
            compat = (assets / 'compatibility-base-current' / case / candidate
                      if label == 'base-current' else assets / f'{name}-{candidate}-compatibility')
            saved = (assets / 'saved-base-current' / case / candidate / 'v0001'
                     if label == 'base-current' else assets / f'{name}-{candidate}-saved/v0001')
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
            if label in ('update095', 'base-current'):
                source_rows = (saved/'analysis/native-actors.jsonl').read_text().splitlines()
                if len(source_rows) != 600 or any(
                        'scene_actor_inventory' not in json.loads(row)
                        for row in source_rows):
                    raise ValueError(f'Scoped original inventory missing: {stem}')
                for channel in ('hazard_actor_state', 'ego_hazard_gap_history',
                                'governing_control_readback'):
                    path = saved/'analysis/channels'/f'{channel}.jsonl'
                    samples = [json.loads(line) for line in path.read_text().splitlines()]
                    if len(samples) != 600:
                        raise ValueError(f'Judgment channel incomplete: {stem}/{channel}')
                    if ((name != 'safe_operation_stop' and channel in
                         ('hazard_actor_state', 'ego_hazard_gap_history')) or
                            (name != 'law_required_stop' and channel == 'governing_control_readback')):
                        if any(sample['value'].get('absence_claimed') is not False
                               for sample in samples):
                            raise ValueError(f'Unjustified source absence claim: {stem}/{channel}')
            copied = {}
            for kind, source in artifacts.items():
                destination = HERE / f'{stem}-{kind}.json' if kind in ('selection', 'compatibility', 'processing') else HERE / f'{stem}-{kind}.log'
                shutil.copyfile(source, destination)
                copied[kind] = {'path': destination.name, 'sha256': sha(destination)}
            for phase in ('offline', 'compatibility', 'saved'):
                log = HERE / (f'base-current-{case}-{candidate}-{phase}.log'
                              if label == 'base-current' else f'{stem}-{phase}.log')
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
    target = HERE / f'{label}-candidate-matrix-audit.json'
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', choices=('update092', 'update095', 'base-current'), default='base-current')
    print(audit(parser.parse_args().label))
