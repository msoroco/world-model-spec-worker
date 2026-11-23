"""Independently bind remaining combined-manifest diagnostic candidate chains."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST_PATH = HERE / 'current-combined-delivery-draft.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit_group(group):
    manifest = read(MANIFEST_PATH)
    runtime_sha = sha(REPO / 'runtime/pipeline/SOURCE-MANIFEST.json')
    case_id = HERE.name + '__' + group
    entry = next((row for row in manifest['cases'] if row['case_id'] == case_id), None)
    require(entry is not None and manifest['assignment_id'] == HERE.name and
            manifest['runtime_manifest_sha256'] == runtime_sha and
            len(manifest['cases']) == 8 and entry['kind'] == 'delivery' and
            len(entry['candidates']) == 3,
            'Combined manifest case or runtime differs: ' + group)
    candidates = [{'id': 'primary', 'construction': entry['construction'],
                   'construction_sha256': entry['construction_sha256']}] + entry['candidates']
    proofs = {}
    for candidate in candidates:
        ident = candidate['id']
        label = group + '/' + ident
        require(sha(HERE / candidate['construction']) ==
                candidate['construction_sha256'],
                'Combined construction differs: ' + label)
        prefix = 'current-combined-' + group + '-' + ident
        offline_path = HERE / (prefix + '-offline-selection.json')
        compatibility_path = HERE / (prefix + '-compatibility.log')
        negative_path = HERE / (prefix + '-negative-analysis.log')
        saved_path = HERE / (prefix + '-saved.log')
        offline, compatibility, saved = [read(path) for path in
                                         (offline_path, compatibility_path, saved_path)]
        attempt = REPO / '.runtime-work' / ('c201084-combined-' + group + '-' +
                                           ident + '-compatibility')
        require(offline['case_id'] == case_id and
                offline['candidate_id'] == ident and
                offline['manifest_sha256'] == sha(MANIFEST_PATH) and
                offline['construction_sha256'] == candidate['construction_sha256'] and
                sha(attempt / 'candidate-selection.json') == sha(offline_path),
                'Combined offline selection differs: ' + label)
        require(compatibility['case_id'] == case_id and
                compatibility['candidate_id'] == ident and
                compatibility['construction_sha256'] == candidate['construction_sha256'] and
                compatibility['runtime_manifest_sha256'] == runtime_sha and
                compatibility['passed'] is True and
                compatibility['negative_removed'] and
                compatibility['negative_error_contains'].startswith('Missing required source:') and
                compatibility['negative_log_sha256'] == sha(negative_path),
                'Combined compatibility or negative proof differs: ' + label)
        require(saved['case_id'] == case_id and
                saved['candidate_id'] == ident and
                saved['passed'] is True and saved['recorded_only'] is True and
                saved['originals_preserved'] is True and
                saved['missing_evidence'] is False and
                saved['physical_acceptance_claimed'] is False and
                saved['legal_acceptance_claimed'] is False and
                saved['analysis_revision']['construction_sha256'] ==
                    candidate['construction_sha256'] and
                saved['analysis_revision']['runtime_manifest_sha256'] == runtime_sha,
                'Combined saved-processing proof differs: ' + label)
        sources = [source for source in compatibility['fixture_manifest']
                   if not source.startswith('capture/') and not source.endswith('.mkv')]
        require({'native-actors.jsonl', 'native-survey-readback.json',
                 'video_frames.jsonl', 'road.xodr'} <= set(sources),
                'Combined retained source inventory incomplete: ' + label)
        for source in sources:
            digest = sha(attempt / source)
            require(compatibility['fixture_manifest'][source] == digest and
                    saved['original_source_hashes'].get(source) == digest,
                    'Combined retained source differs: ' + label + '/' + source)
        for camera in CAMERAS:
            source = camera + '.mkv'
            require(saved['original_source_hashes'].get(source) ==
                    sha(attempt / source),
                    'Combined retained camera differs: ' + label + '/' + source)
        proofs[ident] = {'construction_sha256': candidate['construction_sha256'],
                         'offline_selection_sha256': sha(offline_path),
                         'compatibility_receipt_sha256': sha(compatibility_path),
                         'negative_log_sha256': sha(negative_path),
                         'saved_receipt_sha256': sha(saved_path)}
    require(set(proofs) == {'primary', 'fallback1', 'fallback2', 'fallback3'},
            'Combined candidate coverage incomplete: ' + group)
    return {'format': 'c201084-combined-group-binding-v1', 'passed': True,
            'diagnostic_only': True, 'case_id': case_id,
            'combined_manifest_sha256': sha(MANIFEST_PATH),
            'runtime_manifest_sha256': runtime_sha, 'candidate_proofs': proofs,
            'delivery_selected': False, 'original_native_verified': False,
            'physical_or_legal_completion_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('groups', nargs='+')
    args = parser.parse_args()
    for group in args.groups:
        path = HERE / ('current-combined-' + group + '-binding-audit.json')
        path.write_text(json.dumps(audit_group(group), indent=2, sort_keys=True) + '\n')
        print(group, 'passed')


if __name__ == '__main__':
    main()
