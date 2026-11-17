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
CASES = {
    'tour_bus_at': 'c150142-tour-bus-pinned-saved-at-result-v1',
    'mail_adjacent_deposit': 'c150142-mail-adjacent-primary-result-v3',
    'armored_car_signed_business': 'c150142-merged-armored-signed-business-primary-result-v1',
}


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
