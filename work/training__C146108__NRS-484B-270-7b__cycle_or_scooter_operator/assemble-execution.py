"""Bind six exact CPU candidate receipts into a partial delivery manifest."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
TAGS = {'bicycle_pass_wide': 'bicycle',
        'electric_bicycle_pass_wide': 'ebike-wide',
        'electric_bicycle_pass_narrow': 'ebike-narrow'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return str(target.relative_to(ROOT)), sha(target)


def acquisition(construction):
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    required = set(config['required_atoms']) | {channel['name'] for channel in
                construction['recording_description']['channels']}
    return {name: {'entrypoint': 'runner.py',
        'method': 'original actor body/pose and frame-joined camera acquisition; electric-bicycle class is an authored surrogate pending Native qualification',
        'evidence': ['participant-poses.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                     'pass-context.json', 'overview.mkv', 'approach.mkv',
                     'reference_corner.mkv', 'driver_reference.mkv']}
        for name in sorted(required)}


def main():
    manifest = json.loads((ROOT / 'selected-public-draft-manifest.json').read_text())
    report = {'format': 'c146108-selected-cpu-evidence-v2', 'assignment_id': ROOT.name,
              'scope': 'synthetic software diagnostics only; Native physical and legal acceptance unclaimed',
              'cases': []}
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(ROOT.name + '__')
        family = 'draft-bicycle' if suffix.startswith('bicycle') else 'draft-ebike'
        construction_path = ROOT / family / suffix / 'primary/construction.json'
        construction = json.loads(construction_path.read_text())
        entry['acquisition'] = acquisition(construction)
        target = ROOT / 'selected-proofs' / suffix
        for candidate in ('primary', 'fallback1'):
            candidate_entry = entry if candidate == 'primary' else entry['candidates'][0]
            revision = 'final2' if suffix == 'bicycle_pass_wide' else 'final3'
            source = REPO / '.runtime-work' / ('c146108-' + revision + '-public-' + suffix + '-' + candidate)
            offline = REPO / '.runtime-work' / ('c146108-final3-offline-' + suffix + '-' + candidate)
            proof = target / candidate
            receipt, receipt_sha = copy(source / 'compatibility.json', proof / 'compatibility.json')
            public_log, public_sha = copy(source / 'compatibility-analysis.log', proof / 'public-analysis.log')
            negative_log, negative_sha = copy(source / 'negative-analysis.log', proof / 'negative-analysis.log')
            offline_log, offline_sha = copy(offline / 'offline.log', proof / 'offline.log')
            compatibility = json.loads((ROOT / receipt).read_text())
            assert compatibility['passed'] and compatibility['candidate_id'] == candidate
            assert compatibility['construction_sha256'] == candidate_entry['construction_sha256']
            assert compatibility['log_sha256'] == public_sha
            assert compatibility['negative_log_sha256'] == negative_sha
            candidate_entry['offline'] = {'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' +
                ROOT.name + '/selected-public-draft-manifest.json --case ' + entry['case_id'] +
                ' --candidate ' + candidate + ' --output .runtime-work/c146108-final3-offline-' + suffix +
                '-' + candidate + ' --python $PWD/.venv-cpu/bin/python',
                'construction_sha256': candidate_entry['construction_sha256'],
                'exit_code': 0, 'log': offline_log, 'log_sha256': offline_sha}
            candidate_entry['compatibility'] = {'receipt': receipt, 'sha256': receipt_sha,
                                                 'log': public_log, 'negative_log': negative_log}
            if candidate == 'primary':
                entry['negative'] = {'log': negative_log}
            report['cases'].append({'case_id': entry['case_id'], 'candidate_id': candidate,
                'construction_sha256': candidate_entry['construction_sha256'],
                'offline_log_sha256': offline_sha, 'compatibility_sha256': receipt_sha,
                'negative_log_sha256': negative_sha})
        physical = ROOT / 'selected-physical' / suffix / 'physical-preparation.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(ROOT)),
                                         'sha256': sha(physical)}
        saved = REPO / '.runtime-work' / ('c146108-saved-final3-' + TAGS[suffix]) / 'v0001'
        saved_receipt, saved_sha = copy(saved / 'processing.json', target / 'saved-processing.json')
        saved_log, saved_log_sha = copy(saved / 'analysis.log', target / 'saved-analysis.log')
        processing = json.loads((ROOT / saved_receipt).read_text())
        assert processing['passed'] and processing['recorded_only'] and processing['originals_preserved']
        assert processing['native_revision']['construction_sha256'] == entry['construction_sha256']
        assert processing['analysis_log_sha256'] == saved_log_sha
        entry['saved_processing'] = {'receipt': saved_receipt, 'sha256': saved_sha,
            'recorded_only': True, 'originals_preserved': True,
            'log': saved_log, 'log_sha256': saved_log_sha}
        tag = TAGS[suffix]
        script = ROOT / 'delivery_audit.py'
        positive = ROOT / 'selected-physical' / suffix / 'delivery-audit-positive.log'
        negative = ROOT / 'selected-physical' / suffix / 'delivery-audit-negative.log'
        command = ('.venv-cpu/bin/python -B work/' + ROOT.name + '/delivery_audit.py --case ' +
                   entry['case_id'] + ' --attempt .runtime-work/c146108-saved-attempt-final3-' +
                   tag + ' --diagnostic')
        entry['delivery_acceptance'] = {'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': str(script.relative_to(ROOT)), 'script_sha256': sha(script),
            'command': command, 'test_exit_code': 0,
            'test_log': str(positive.relative_to(ROOT)), 'test_log_sha256': sha(positive),
            'negative_command': command.removesuffix(' --diagnostic'),
            'negative_exit_code': 1,
            'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
            'negative_log': str(negative.relative_to(ROOT)),
            'negative_log_sha256': sha(negative)}
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' +
                ROOT.name + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $ATTEMPT/owner-release.json',
            'feedback_command': 'cat "$SAVED_OUTPUT"/v0001/feedback.json',
            'test_exit_code': 0, 'test_log': saved_log, 'test_log_sha256': saved_log_sha}
    manifest['status'] = 'partial_cpu_diagnostic'
    manifest['delivery_ready'] = False
    write(ROOT / 'execution-manifest.json', manifest)
    write(ROOT / 'selected-evidence.json', report)
    print(json.dumps({'cases': len(manifest['cases']), 'candidate_receipts': len(report['cases']),
                      'manifest_sha256': sha(ROOT / 'execution-manifest.json'),
                      'evidence_sha256': sha(ROOT / 'selected-evidence.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
