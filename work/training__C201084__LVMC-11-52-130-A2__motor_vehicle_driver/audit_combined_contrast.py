"""Independently bind first combined-manifest CPU chain and source identity."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__contrast'
ATTEMPT = REPO / '.runtime-work/c201084-combined-contrast-primary-compatibility'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit():
    path = HERE / 'current-combined-delivery-draft.json'
    manifest = read(path)
    runtime_sha = sha(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    require(manifest['assignment_id'] == HERE.name and
            manifest['runtime_manifest_sha256'] == runtime_sha and
            len(manifest['cases']) == 8 and
            len({entry['case_id'] for entry in manifest['cases']}) == 8,
            'Combined manifest identity or coverage differs')
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    construction_sha = sha(HERE / entry['construction'])
    require(entry['construction_sha256'] == construction_sha and
            entry['kind'] == 'delivery' and len(entry['candidates']) == 3,
            'Combined contrast construction differs')
    selection_path = HERE / 'current-combined-contrast-primary-offline-selection.json'
    selection = read(selection_path)
    require(selection['case_id'] == CASE and
            selection['candidate_id'] == 'primary' and
            selection['construction_sha256'] == construction_sha and
            selection['manifest_sha256'] == sha(path),
            'Combined offline selection differs')
    fallback_selections = {}
    for candidate in entry['candidates']:
        ident = candidate['id']
        candidate_path = HERE / ('current-combined-contrast-' + ident +
                                 '-offline-selection.json')
        selected = read(candidate_path)
        require(sha(HERE / candidate['construction']) ==
                candidate['construction_sha256'] and
                selected['case_id'] == CASE and
                selected['candidate_id'] == ident and
                selected['construction_sha256'] ==
                candidate['construction_sha256'] and
                selected['manifest_sha256'] == sha(path),
                'Combined fallback offline selection differs: ' + ident)
        fallback_selections[ident] = sha(candidate_path)
    compatibility_path = HERE / 'current-combined-contrast-primary-compatibility.log'
    compatibility = read(compatibility_path)
    require(compatibility['case_id'] == CASE and
            compatibility['candidate_id'] == 'primary' and
            compatibility['construction_sha256'] == construction_sha and
            compatibility['runtime_manifest_sha256'] == runtime_sha and
            compatibility['passed'] is True and
            compatibility['negative_removed'] == 'native-survey-readback.json' and
            compatibility['negative_error_contains'] ==
                'Missing required source: native-survey-readback.json' and
            compatibility['negative_log_sha256'] == sha(
                HERE / 'current-combined-contrast-primary-negative-analysis.log'),
            'Combined compatibility or negative proof differs')
    saved_path = HERE / 'current-combined-contrast-primary-saved.log'
    saved = read(saved_path)
    require(saved['case_id'] == CASE and saved['candidate_id'] == 'primary' and
            saved['passed'] is True and saved['recorded_only'] is True and
            saved['originals_preserved'] is True and
            saved['missing_evidence'] is False and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False and
            saved['analysis_revision']['construction_sha256'] == construction_sha and
            saved['analysis_revision']['runtime_manifest_sha256'] == runtime_sha,
            'Combined saved-processing proof differs')
    sources = ('native-actors.jsonl', 'video_frames.jsonl',
               'native-survey-readback.json', 'road.xodr')
    for source in sources:
        digest = sha(ATTEMPT / source)
        require(compatibility['fixture_manifest'].get(source) == digest and
                saved['original_source_hashes'].get(source) == digest,
                'Combined retained source differs: ' + source)
    cameras = ('overview', 'approach', 'reference_corner', 'driver_reference')
    for camera in cameras:
        source = camera + '.mkv'
        require(saved['original_source_hashes'].get(source) == sha(ATTEMPT / source),
                'Combined saved camera differs: ' + camera)
    fallback_proofs = {}
    for candidate in entry['candidates']:
        fallback_id = candidate['id']
        fallback_attempt = (REPO / '.runtime-work' /
                            ('c201084-combined-contrast-' + fallback_id + '-compatibility'))
        prefix = 'current-combined-contrast-' + fallback_id
        fallback_compatibility_path = HERE / (prefix + '-compatibility.log')
        fallback_compatibility = read(fallback_compatibility_path)
        fallback_negative_path = HERE / (prefix + '-negative-analysis.log')
        require(fallback_compatibility['case_id'] == CASE and
                fallback_compatibility['candidate_id'] == fallback_id and
                fallback_compatibility['construction_sha256'] == candidate['construction_sha256'] and
                fallback_compatibility['runtime_manifest_sha256'] == runtime_sha and
                fallback_compatibility['passed'] is True and
                fallback_compatibility['negative_removed'] == 'native-survey-readback.json' and
                fallback_compatibility['negative_log_sha256'] == sha(fallback_negative_path),
                'Combined ' + fallback_id + ' compatibility or negative proof differs')
        fallback_saved_path = HERE / (prefix + '-saved.log')
        fallback_saved = read(fallback_saved_path)
        require(fallback_saved['case_id'] == CASE and
                fallback_saved['candidate_id'] == fallback_id and
                fallback_saved['passed'] is True and
                fallback_saved['recorded_only'] is True and
                fallback_saved['originals_preserved'] is True and
                fallback_saved['missing_evidence'] is False and
                fallback_saved['physical_acceptance_claimed'] is False and
                fallback_saved['legal_acceptance_claimed'] is False and
                fallback_saved['analysis_revision']['construction_sha256'] ==
                    candidate['construction_sha256'] and
                fallback_saved['analysis_revision']['runtime_manifest_sha256'] == runtime_sha,
                'Combined ' + fallback_id + ' saved-processing proof differs')
        for source in sources:
            digest = sha(fallback_attempt / source)
            require(fallback_compatibility['fixture_manifest'].get(source) == digest and
                    fallback_saved['original_source_hashes'].get(source) == digest,
                    'Combined ' + fallback_id + ' retained source differs: ' + source)
        for camera in cameras:
            source = camera + '.mkv'
            require(fallback_saved['original_source_hashes'].get(source) ==
                    sha(fallback_attempt / source),
                    'Combined ' + fallback_id + ' saved camera differs: ' + camera)
        fallback_proofs[fallback_id] = {
            'compatibility_receipt_sha256': sha(fallback_compatibility_path),
            'negative_log_sha256': sha(fallback_negative_path),
            'saved_receipt_sha256': sha(fallback_saved_path)}
    return {'format': 'c201084-combined-contrast-cpu-binding-v1',
            'passed': True, 'diagnostic_only': True,
            'manifest_sha256': sha(path),
            'construction_sha256': construction_sha,
            'offline_selection_sha256': sha(selection_path),
            'fallback_offline_selection_sha256': fallback_selections,
            'compatibility_receipt_sha256': sha(compatibility_path),
            'saved_receipt_sha256': sha(saved_path),
            'fallback_proofs': fallback_proofs,
            'source_sha256': {source: sha(ATTEMPT / source) for source in sources},
            'camera_sha256': {camera: sha(ATTEMPT / (camera + '.mkv'))
                              for camera in cameras},
            'delivery_selected': False,
            'original_native_verified': False,
            'physical_or_legal_completion_claimed': False}


if __name__ == '__main__':
    (HERE / 'current-combined-contrast-binding-audit.json').write_text(
        json.dumps(audit(), indent=2, sort_keys=True) + '\n')
