"""Diagnostic source tests for the exception part of delivery_audit.py."""
import hashlib
import json
import tempfile
from pathlib import Path

from delivery_audit import (audit, lines, read, validate_exception_measurement,
                            validate_rows)


ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]
PLAN = json.loads((WORK / 'case-plan.json').read_text())
MANIFEST_PATH = WORK / 'execution-manifest.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())
MANIFEST_SHA256 = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
SELECTED = {item['case_id']: item for item in MANIFEST['cases']}
CASES = {
    **{
        f'{service}_{boundary}':
            f'c150142-selected-{service.replace("_", "-")}-{boundary.replace("_", "-")}-primary-result-v1'
        for service in ('tour_bus', 'shuttle_bus', 'limo', 'rtc_bus')
        for boundary in ('below', 'at', 'above', 'no_loading')
    },
    **{
        item['case_id'].split('__')[-1]:
            'c150142-selected-' + item['case_id'].split('__')[-1] +
            '-primary-canonicalnext-v1-result'
        for item in MANIFEST['cases']
        if item['case_id'].split('__')[-1].startswith(
            ('mail_', 'armored_car_', 'emergency_vehicle_'))
    },
}
CASES['tour_bus_below'] = 'c150142-selected-tour-bus-below-primary-result-v3'
CASES['rtc_bus_below'] = 'c150142-selected-rtc-bus-below-primary-result-v2'


def reject(call, message):
    try:
        call()
    except ValueError as error:
        assert message in str(error), (message, str(error))
        return
    raise AssertionError('accepted invalid exception evidence: ' + message)


def write(path, data):
    path.unlink(missing_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + '\n')


def stage(source, folder):
    report = json.loads((source / 'analysis-report.json').read_text())
    names = {'config.json', 'result.json', 'analysis-report.json',
             'native-map-readback.json', 'native-raw-actors.jsonl'}
    names.update(report['measurements']['signed_curb_observation']['sources'])
    for name in names:
        (folder / name).symlink_to((source / name).resolve())


def main():
    passed = {}
    with tempfile.TemporaryDirectory(prefix='c150142-exception-audit-',
                                     dir=ROOT / '.runtime-work') as tmp:
        root = Path(tmp)
        for slug, dirname in CASES.items():
            source = ROOT / '.runtime-work' / dirname / 'v0001/analysis'
            folder = root / slug
            folder.mkdir()
            stage(source, folder)
            case = WORK.name + '__' + slug
            selection = read(source / 'candidate-selection.json')
            assert selection['case_id'] == case
            assert selection['candidate_id'] == 'primary'
            assert selection['manifest_sha256'] == MANIFEST_SHA256
            assert selection['construction_sha256'] == SELECTED[case]['construction_sha256']
            checked = validate_exception_measurement(
                folder, PLAN, case, 'synthetic_native_sample')
            joined = validate_rows(lines(source / 'native-raw-actors.jsonl'),
                                   lines(source / 'video_frames.jsonl'),
                                   lines(source / 'trace.jsonl'),
                                   read(source / 'native-map-readback.json'),
                                   case, checked['frames'],
                                   'synthetic_native_sample', True)
            assert joined['red_curb_stop_or_park_observed'] is True
            passed[slug] = checked['frames']
            reject(lambda: audit(case, 1, 1, source.parent.name, source,
                                 folder / 'review.json', source / 'raw.mkv',
                                 folder / 'decode.json', source / 'audit.json'),
                   'Missing delivery source:')
            reject(lambda: validate_exception_measurement(folder, PLAN, case),
                   'provenance or declared context differs')
            if slug == 'mail_adjacent_deposit':
                config = json.loads((folder / 'config.json').read_text())
                config['service_class'] = 'emergency_vehicle'
                write(folder / 'config.json', config)
                reject(lambda: validate_exception_measurement(
                    folder, PLAN, case, 'synthetic_native_sample'),
                    'declared context differs')
                (folder / 'config.json').unlink()
                (folder / 'config.json').symlink_to((source / 'config.json').resolve())
                map_data = json.loads((folder / 'native-map-readback.json').read_text())
                map_data['mailbox_readback']['present'] = False
                write(folder / 'native-map-readback.json', map_data)
                reject(lambda: validate_exception_measurement(
                    folder, PLAN, case, 'synthetic_native_sample'),
                    'sign/mailbox readback differs')
                (folder / 'native-map-readback.json').unlink()
                (folder / 'native-map-readback.json').symlink_to(
                    (source / 'native-map-readback.json').resolve())
                report = json.loads((folder / 'analysis-report.json').read_text())
                result = json.loads((folder / 'result.json').read_text())
                report['measurements']['signed_curb_observation']['value'][
                    'red_curb_stationary_duration_s'] = 11.0
                result['measured_values']['signed_curb_observation'][
                    'red_curb_stationary_duration_s'] = 11.0
                write(folder / 'analysis-report.json', report)
                write(folder / 'result.json', result)
                reject(lambda: validate_exception_measurement(
                    folder, PLAN, case, 'synthetic_native_sample'),
                    'measured stationary duration differs')
                (folder / 'analysis-report.json').unlink()
                (folder / 'result.json').unlink()
                for name in ('analysis-report.json', 'result.json'):
                    (folder / name).symlink_to((source / name).resolve())
                participant = 'native-mail-worker-actors.jsonl'
                rows = (folder / participant).read_text().splitlines()
                (folder / participant).unlink()
                (folder / participant).write_text('\n'.join(rows[:-1]) + '\n')
                report = json.loads((folder / 'analysis-report.json').read_text())
                report['measurements']['signed_curb_observation']['sources'][participant] = (
                    hashlib.sha256((folder / participant).read_bytes()).hexdigest())
                write(folder / 'analysis-report.json', report)
                reject(lambda: validate_exception_measurement(
                    folder, PLAN, case, 'synthetic_native_sample'),
                    'participant Native frame join differs')
    print(json.dumps({'format': 'c150142-exception-audit-cpu-proof-v1',
                      'diagnostic_cases': passed,
                      'rejected': ['missing_capture_report', 'synthetic_default',
                                   'wrong_service_class',
                                   'changed_mailbox', 'wrong_duration',
                                   'missing_participant_frame'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
