"""Bind completed selected CPU receipts without claiming original delivery."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
ASSIGNMENT = FOLDER.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads((FOLDER/'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('_', 1)[-1]
        case = entry['case_id']
        entry['physical_preparation']['sha256'] = sha(HERE/f'physical-{suffix}-receipt.json')
        for candidate in [entry, entry['candidates'][0]]:
            candidate['offline']['log_sha256'] = sha(FOLDER/candidate['offline']['log'])
        positive = HERE/f'selected-{suffix}-saved-processing.json'
        negative = HERE/f'selected-{suffix}-saved-negative-feedback.json'
        saved_log = HERE/f'selected-{suffix}-saved-test.log'
        src_log = ROOT/f'.runtime-work/c385967-saved2-{suffix}.log'
        if not all(p.is_file() for p in (positive, negative, src_log)):
            raise ValueError('Selected saved proof missing: ' + suffix)
        shutil.copyfile(src_log, saved_log)
        saved = json.loads(positive.read_text())
        feedback = json.loads(negative.read_text())
        if not (saved.get('passed') is True and saved.get('recorded_only') is True
                and saved.get('missing_evidence') is False
                and saved.get('timestamp_joins', {}).get('frames') == 600
                and feedback.get('recorded_only') is True
                and feedback.get('native_replay_requested') is False):
            raise ValueError('Selected saved receipt incomplete')
        script = 'native/delivery_audit.py'
        deliver = {'case_id':case, 'sets':['full-train'],
            'checks':['native_source','all_participants','time_join',
                      'full_video_decode','actual_pixels','physical_completion'],
            'script':script,'script_sha256':sha(FOLDER/script),
            'command':f'.venv-cpu/bin/python work/{ASSIGNMENT}/{script} --case {case} --selftest',
            'test_exit_code':0,'test_log':f'native/delivery-{suffix}-positive.log',
            'test_log_sha256':sha(HERE/f'delivery-{suffix}-positive.log'),
            'negative_command':f'.venv-cpu/bin/python work/{ASSIGNMENT}/{script} --case {case} --negative-selftest',
            'negative_exit_code':1,
            'negative_expected_error':'Reviewed pixel box exceeds source video',
            'negative_log':f'native/delivery-{suffix}-negative.log',
            'negative_log_sha256':sha(HERE/f'delivery-{suffix}-negative.log'),
            'scope':'synthetic CPU mechanics; original City authority and source review remain'}
        entry['delivery_acceptance'] = deliver
        entry['post_capture'] = {'recorded_only':True,
            'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{ASSIGNMENT}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR',
            'feedback_command':f'cat $OUTPUT/v0001/feedback.json # {case}',
            'test_exit_code':0,'test_log':f'native/{saved_log.name}',
            'test_log_sha256':sha(saved_log),
            'positive_processing_receipt':f'native/{positive.name}',
            'positive_processing_sha256':sha(positive),
            'missing_source_feedback':f'native/{negative.name}',
            'missing_source_feedback_sha256':sha(negative),
            'scope':'source-shaped synthetic saved positive and missing-permission-source negative; original physical recording unverified'}
    write(FOLDER/'execution-manifest.json', manifest)
    root_log = HERE/'root-cpu-tests.log'
    tests = [{'command':f'cd work/{ASSIGNMENT} && PYTHONPATH=. ../../.venv-cpu/bin/python -B -m unittest discover -s tests -v',
              'exit_code':0,'log':f'native/{root_log.name}','sha256':sha(root_log)}]
    for suffix in 'ab':
        log = HERE/f'selected-{suffix}-saved-test.log'
        tests.append({'command':f'.venv-cpu/bin/python -B work/{ASSIGNMENT}/native/prove_saved_selected.py --condition {suffix} --validator .runtime-work/c229597-library-current/.lake/build/bin/adapterCheck',
            'exit_code':0,'log':f'native/{log.name}','sha256':sha(log)})
    result = json.loads((FOLDER/'result.json').read_text())
    result.update(status='ready',reason=None,readiness_kind='delivery_prepared',
        counts={'source_topics':3,'selected_comparison_cases_planned':2,
            'comparisons_planned':1,'delivery_cases_prepared':2,
            'candidates_proven':2,'accepted_equivalence_reuses':0,
            'accepted_membership_rows':0}, tests=tests,
        current_cpu_proof={'manifest':'execution-manifest.json',
            'semantic_index':'proposals/semantic-index.json',
            'comparison_positive':'native/comparison-positive.json',
            'comparison_missing_source_negative':'native/comparison-negative.log',
            'saved_positive_and_negative_cases':['a','b'],
            'native_executed':False,'physical_acceptance_claimed':False},
        first_gpu_delivery_command=f'.venv-cpu/bin/python runtime.py execute-delivery --python "$CARLA_PYTHON" --host "$CARLA_HOST" --port "$CARLA_PORT" --case {ASSIGNMENT}__probe_a --job "$JOB_ID" --db "$DB" --run "$RUN" --assignment {ASSIGNMENT}',
        remaining_gpu_checks=['Original City Traffic Engineer designation document and actual marking review',
            'Actual parked body pose and one-way lawful direction readback',
            'Original four-view video decode and pixel review',
            'Independent full-train acceptance and paired orientation comparison'])
    write(FOLDER/'result.json',result)
    print(json.dumps({'manifest_sha256':sha(FOLDER/'execution-manifest.json'),
        'result_sha256':sha(FOLDER/'result.json')},sort_keys=True))


if __name__ == '__main__':
    main()
