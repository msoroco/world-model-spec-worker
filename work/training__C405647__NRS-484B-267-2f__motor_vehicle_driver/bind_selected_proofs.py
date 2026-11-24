"""Bind selected case proofs without claiming full-branch readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def relative(path):
    return path.relative_to(HERE).as_posix()


def main():
    current = read(HERE / 'current-execution-manifest.json')
    public = read(HERE / 'current-public/public-matrix.json')
    saved = read(HERE / 'current-public/saved-matrix.json')
    if not public['all_passed'] or not saved['all_passed']:
        raise ValueError('Selected public or saved-only matrix did not pass')
    public_results = list(public['results'])
    saved_results = list(saved['results'])
    if any(entry['case_id'].endswith('__official_approach') for entry in current['cases']):
        official_public = read(HERE / 'current-public/official-matrix.json')
        official_saved = read(HERE / 'current-public/official-saved-matrix.json')
        if not official_public['all_passed'] or not official_saved['all_passed']:
            raise ValueError('Official selected public or saved-only matrix did not pass')
        public_results.extend(official_public['results'])
        saved_results.extend(official_saved['results'])
    if any(entry['case_id'].endswith('__stopped_referral') for entry in current['cases']):
        stopped_public = read(HERE / 'current-public/stopped-matrix.json')
        stopped_saved = read(HERE / 'current-public/stopped-saved-matrix.json')
        if not stopped_public['all_passed'] or not stopped_saved['all_passed']:
            raise ValueError('Stopped selected public or saved-only matrix did not pass')
        public_results.extend(stopped_public['results'])
        saved_results.extend(stopped_saved['results'])
    if any(entry['case_id'].endswith('__visible_movement') for entry in current['cases']):
        visible_public = read(HERE / 'current-public/visible-matrix.json')
        visible_saved = read(HERE / 'current-public/visible-saved-matrix.json')
        if not visible_public['all_passed'] or not visible_saved['all_passed']:
            raise ValueError('Visible movement public or saved-only matrix did not pass')
        public_results.extend(visible_public['results'])
        saved_results.extend(visible_saved['results'])
    for suffix, public_name, saved_name in (
        ('visible_hand_signal', 'hand-matrix.json', 'hand-saved-matrix.json'),
        ('officer_direction', 'officer-direction-matrix.json',
         'officer-direction-saved-matrix.json'),
    ):
        if any(entry['case_id'].endswith('__' + suffix) for entry in current['cases']):
            variant_public = read(HERE / 'current-public' / public_name)
            variant_saved = read(HERE / 'current-public' / saved_name)
            if not variant_public['all_passed'] or not variant_saved['all_passed']:
                raise ValueError('Selected variant public or saved proof failed: ' + suffix)
            public_results.extend(variant_public['results'])
            saved_results.extend(variant_saved['results'])
    pr = {(r['case'], r['candidate']): r for r in public_results}
    sr = {(r['case_id'], r['candidate_id']): r for r in saved_results}
    for entry in current['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(AID + '__')
        proof = HERE / 'physical-proof' / suffix / 'proof.json'
        if read(proof)['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical diagnostic construction differs')
        entry['physical_preparation'] = {'case_id': case_id,
                                         'receipt': relative(proof), 'sha256': sha(proof)}
        construction = read(HERE / entry['construction'])
        channels = [c['name'] for c in construction['recording_description']['channels']]
        source = 'original vehicle_poses.jsonl, video_frames.jsonl, emergency_context.json, four synchronized MKV cameras'
        if suffix == 'visible_hand_signal':
            source += ', driver_hand_track.jsonl and hand_signal_review.json'
        elif suffix == 'officer_direction':
            source += ', officer_track.jsonl and officer_direction.json'
        entry['acquisition'] = {name: {'entrypoint': 'runner.py',
                                       'evidence': source,
                                       'method': '600-frame original Native pose, body, light-state, context and camera join; synthetic CPU fixture is diagnostic only'}
                                for name in channels}
        for candidate in ['primary', *entry['candidates']]:
            cid = candidate if candidate == 'primary' else candidate['id']
            dest = entry if cid == 'primary' else candidate
            key = (case_id, cid)
            pub = pr[key]
            save = sr[key]
            if pub['exit_code'] != 0 or save['exit_code'] != 0 or pub['construction_sha256'] != dest['construction_sha256']:
                raise ValueError('Candidate proof differs: ' + suffix + '/' + cid)
            base = suffix + '-' + cid
            offline = HERE / 'current-public' / (base + '-offline.log')
            receipt = HERE / pub['files']['compatibility.json']['path']
            negative = HERE / pub['files']['negative.log']['path']
            analysis = HERE / pub['files']['analysis.log']['path']
            processed = HERE / save['receipt']
            if any(not q.is_file() for q in (offline, receipt, negative, analysis, processed)):
                raise ValueError('Candidate proof file missing: ' + base)
            offline_version = {'official_approach': 'offline-v4-', 'stopped_referral': 'offline-v2-'}.get(suffix, 'offline-v3-')
            offline_attempt = ('offline-visible-draft-primary' if suffix == 'visible_movement'
                               else 'offline-hand-signal-draft-primary-v2' if suffix == 'visible_hand_signal'
                               else 'offline-officer-draft-primary' if suffix == 'officer_direction'
                               else offline_version + base)
            dest['offline'] = {'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID + '/current-execution-manifest.json --case ' + case_id + ' --candidate ' + cid + ' --output .runtime-work/c405647-267-2f/' + offline_attempt + ' --python "$PWD/.venv-cpu/bin/python"',
                               'exit_code': 0, 'construction_sha256': dest['construction_sha256'],
                               'log': relative(offline), 'log_sha256': sha(offline)}
            dest['compatibility'] = {'receipt': relative(receipt), 'sha256': sha(receipt),
                                     'log': relative(analysis), 'negative_log': relative(negative)}
            dest['negative'] = {'log': relative(negative)}
            dest['saved_processing'] = {'receipt': relative(processed), 'sha256': sha(processed)}
        primary_processed = HERE / 'current-public' / (suffix + '-primary-processing.json')
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + case_id + ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': relative(primary_processed),
            'test_log_sha256': sha(primary_processed)}
        positive = HERE / 'delivery-proof' / (suffix + '-positive.log')
        negative = HERE / 'delivery-proof' / (suffix + '-negative.log')
        script = HERE / 'delivery_audit.py'
        entry['delivery_acceptance'] = {'case_id': case_id, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': relative(script), 'script_sha256': sha(script),
            'command': '.venv-cpu/bin/python work/' + AID + '/delivery_audit.py --case ' + case_id + ' --diagnostic',
            'negative_command': '.venv-cpu/bin/python work/' + AID + '/delivery_audit.py --case ' + case_id,
            'test_exit_code': 0, 'negative_exit_code': 1,
            'negative_expected_error': 'Original Native source required for delivery acceptance',
            'test_log': relative(positive), 'test_log_sha256': sha(positive),
            'negative_log': relative(negative), 'negative_log_sha256': sha(negative)}
    current['status'] = 'partial_selected_proofs_bound'
    current['delivery_ready'] = False
    target = HERE / 'execution-manifest.json'
    target.write_text(json.dumps(current, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(current['cases']),
                      'candidate_proofs': len(pr), 'manifest_sha256': sha(target),
                      'delivery_ready': False}))


if __name__ == '__main__':
    main()
