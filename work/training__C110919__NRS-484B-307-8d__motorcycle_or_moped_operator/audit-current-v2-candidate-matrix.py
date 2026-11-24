"""Independently bind the eight current-v2 diagnostic construction chains."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def config(bundle):
    return json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))


def audit():
    manifest_path = HERE / 'current-v2-candidate-manifest.json'
    manifest = read(manifest_path)
    if manifest['assignment_id'] != HERE.name or len(manifest['cases']) != 2:
        raise ValueError('Exact two-case diagnostic matrix missing')
    rows = []
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        if condition not in ('condition_a', 'condition_b') or len(entry['candidates']) != 3:
            raise ValueError('Expected primary plus three alternatives')
        primary = read(HERE / entry['construction'])
        primary_config = config(primary)
        for name in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if name == 'primary' else next(item for item in entry['candidates'] if item['id'] == name)
            construction = HERE / selected['construction']
            if sha(construction) != selected['construction_sha256']:
                raise ValueError('Construction hash mismatch')
            bundle = read(construction)
            candidate_config = config(bundle)
            if (bundle['case_id'] != entry['case_id'] or bundle['actor'] != primary['actor']
                    or bundle['cell_id'] != primary['cell_id']
                    or bundle['recording_description'] != primary['recording_description']
                    or candidate_config['cameras'] != primary_config['cameras']
                    or candidate_config['knobs']['camera_profile'] != primary_config['knobs']['camera_profile']):
                raise ValueError('Case, actor, or recording contract drift')
            changed = [key for key in candidate_config['knobs']
                       if candidate_config['knobs'][key] != primary_config['knobs'][key]]
            if name == 'primary' and changed or name != 'primary' and changed != selected['changed_knobs']:
                raise ValueError('Fallback must change exactly its declared knob')
            folder = HERE / 'current-v2-candidates' / condition / name
            compatibility_path = folder / 'compatibility.json'
            compatibility = read(compatibility_path)
            if (compatibility.get('passed') is not True or compatibility['case_id'] != entry['case_id']
                    or compatibility['candidate_id'] != name
                    or compatibility['construction_sha256'] != selected['construction_sha256']
                    or compatibility['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']
                    or len(compatibility['fixture_manifest']) != 614
                    or not {'actual_analysis', 'lean_decoder', 'final_decode', 'selected_measurements',
                            'negative_case_source'} <= set(compatibility['checks'])
                    or sha(folder / 'public-analysis.log') != compatibility['log_sha256']
                    or sha(folder / 'source-negative.log') != compatibility['negative_log_sha256']):
                raise ValueError('Incomplete public positive/negative compatibility')
            saved_path = folder / 'saved-proof.json'
            saved = read(saved_path)
            processed = saved['processing']
            if (saved.get('passed') is not True or saved['manifest_sha256'] != sha(manifest_path)
                    or saved['compatibility_sha256'] != sha(compatibility_path)
                    or saved['construction_sha256'] != selected['construction_sha256']
                    or saved['source_files'] != 614 or saved['source_hashes_preserved'] is not True
                    or processed.get('passed') is not True or processed.get('recorded_only') is not True
                    or processed.get('originals_preserved') is not True
                    or processed.get('candidate_id') != name
                    or processed.get('analysis_revision', {}).get('construction_sha256') != selected['construction_sha256']
                    or processed.get('timestamp_joins', {}).get('frames') != 600
                    or processed.get('final_video_checks', {}).get('frames') != 600
                    or processed.get('physical_acceptance_claimed') is not False
                    or processed.get('legal_acceptance_claimed') is not False
                    or sha(folder / 'saved-command.log') != saved['processing_sha256']):
                raise ValueError('Recorded-only saved proof failed independent binding')
            rows.append({'condition': condition, 'candidate': name,
                         'construction_sha256': sha(construction),
                         'compatibility_sha256': sha(compatibility_path),
                         'source_negative_sha256': sha(folder / 'source-negative.log'),
                         'saved_proof_sha256': sha(saved_path)})
    report = {'format': 'c110919-current-v2-candidate-matrix-audit',
              'passed': True, 'manifest_sha256': sha(manifest_path),
              'rows': rows, 'original_native_observed': False,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    target = HERE / 'current-v2-candidate-matrix-audit.json'
    target.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'rows': len(rows), 'audit_sha256': sha(target)}))


if __name__ == '__main__':
    audit()
