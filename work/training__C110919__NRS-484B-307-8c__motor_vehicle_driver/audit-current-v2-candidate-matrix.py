"""Independently check the six exact candidate software proof bindings."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest_path = HERE / 'current-v2-candidate-manifest.json'
    manifest = read(manifest_path)
    if manifest['runtime_manifest_sha256'] != sha(ROOT / 'runtime/SOURCE-MANIFEST.json'):
        raise ValueError('Runtime manifest changed')
    if len(manifest['cases']) != 2:
        raise ValueError('Expected two same-cell cases')
    output = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        if suffix not in ('probe_a', 'probe_b') or len(entry['candidates']) != 2:
            raise ValueError('Unexpected selected cases or fallback count')
        primary = read(HERE / entry['construction'])
        base_config = read_config(primary)
        for candidate, selected in [('primary', entry), *[(row['id'], row) for row in entry['candidates']]]:
            construction = HERE / selected['construction']
            if sha(construction) != selected['construction_sha256']:
                raise ValueError('Construction hash changed')
            bundle = read(construction)
            if bundle['case_id'] != entry['case_id'] or bundle['recording_description'] != primary['recording_description']:
                raise ValueError('Case/recording changed in fallback')
            config = read_config(bundle)
            differences = [key for key in base_config['knobs'] if base_config['knobs'][key] != config['knobs'][key]]
            if candidate == 'primary' and differences or candidate != 'primary' and differences != selected['changed_knobs']:
                raise ValueError('Fallback changed undeclared knobs')
            folder = HERE / 'current-v2-candidates' / suffix / candidate
            public = read(folder / 'compatibility.json')
            if (public.get('passed') is not True or public.get('case_id') != entry['case_id']
                    or public.get('candidate_id') != candidate or public.get('construction_sha256') != sha(construction)
                    or public.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256']
                    or not {'negative_case_source', 'actual_analysis', 'final_decode', 'four_camera_sources'} <= set(public['checks'])):
                raise ValueError('Public receipt not exact and complete')
            saved = read(folder / 'saved-proof.json')
            processing = saved['processing']
            if (saved.get('passed') is not True or saved['manifest_sha256'] != sha(manifest_path)
                    or saved['construction_sha256'] != sha(construction)
                    or saved['compatibility_sha256'] != sha(folder / 'compatibility.json')
                    or saved['processing_sha256'] != sha(folder / 'saved-command.log')
                    or saved['source_files'] != len(public['fixture_manifest'])
                    or saved.get('source_hashes_preserved') is not True
                    or processing.get('passed') is not True or processing.get('recorded_only') is not True
                    or processing.get('originals_preserved') is not True or processing.get('missing_evidence')
                    or processing.get('timestamp_joins', {}).get('frames') != 600
                    or processing.get('final_video_checks', {}).get('passed') is not True
                    or processing.get('candidate_id') != candidate):
                raise ValueError('Recorded-only saved proof changed')
            if public['negative_error_contains'] not in (folder / 'negative-analysis.log').read_text():
                raise ValueError('Removed-source negative was not retained')
            output.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                           'construction_sha256': sha(construction),
                           'compatibility_sha256': sha(folder / 'compatibility.json'),
                           'negative_log_sha256': sha(folder / 'negative-analysis.log'),
                           'saved_proof_sha256': sha(folder / 'saved-proof.json')})
    receipt = {'format': 'c110919-8c-current-v2-candidate-matrix-audit', 'passed': True,
               'manifest_sha256': sha(manifest_path), 'rows': output,
               'original_native_observed': False, 'physical_acceptance_claimed': False}
    target = HERE / 'current-v2-candidate-matrix-audit.json'
    target.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'rows': len(output), 'audit_sha256': sha(target)}))


def read_config(bundle):
    return json.loads(next(item['content'] for item in bundle['files'] if item['path'] == 'config.json'))


if __name__ == '__main__':
    audit()
