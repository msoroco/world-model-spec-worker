"""Exercise saved-only finalization on explicit synthetic diagnostic inputs."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from yellow_red_finalizer import finalize
from yellow_red_policy import CASES

SOURCE = REPO / '.runtime-work/c158196-yellow-red-source-proof'
ROOT = REPO / '.runtime-work/c158196-yellow-red-finalizer-proof'
BASE = HERE.name


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def stage(suffix):
    attempt = ROOT / suffix
    if attempt.exists():
        shutil.rmtree(attempt)
    attempt.mkdir(parents=True)
    for name in ('signal_vehicle_history.jsonl', 'video_frames.jsonl', 'junction_context.json'):
        shutil.copy2(SOURCE / suffix / name, attempt / name)
    cfg = json.loads((HERE / 'config.json').read_text())
    case_id = BASE + '__' + suffix
    cfg['selected_case_id'] = cfg['case']['case_id'] = case_id
    write(attempt / 'config.json', cfg)
    write(attempt / 'acquisition-provenance.json', {
        'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
        'physical_acceptance_claimed': False,
    })
    with (attempt / 'trace.jsonl').open('x') as stream:
        for line in (attempt / 'signal_vehicle_history.jsonl').read_text().splitlines():
            row = json.loads(line)
            body = row['ego_body_vertices_xy_m']
            stream.write(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                     'position_m': [sum(v[0] for v in body) / 4,
                                                    sum(v[1] for v in body) / 4]}) + '\n')
    return attempt


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    observations = []
    for suffix, target in CASES.items():
        attempt = stage(suffix)
        report = finalize(attempt, attempt / 'analysis-report.json')
        result = json.loads((attempt / 'result.json').read_text())
        onset = report['source_report']['yellow_to_red_onset']['frame']
        entry = report['source_report']['first_body_entry']
        frame = None if entry is None else entry['frame']
        if onset != 160 or frame != target or report['measurements']['target_matched'] is not True:
            raise AssertionError('Saved target/source mismatch: ' + suffix)
        checks = result['physical_checks']
        if checks['setup']['status'] != 'met' or checks['target']['status'] != 'met':
            raise AssertionError('Saved setup/target source check failed: ' + suffix)
        expected_maneuver = 'not_met' if target is None else 'met'
        if checks['maneuver']['status'] != expected_maneuver:
            raise AssertionError('Saved maneuver source check failed: ' + suffix)
        if result['provenance_kind'] != 'synthetic_fixture' or result['physical_acceptance_claimed'] is not False:
            raise AssertionError('Diagnostic provenance misreported')
        observations.append({'case_id': result['case_id'], 'entry_frame': frame,
                             'red_onset_frame': onset, 'setup': checks['setup']['status'],
                             'target': checks['target']['status'],
                             'maneuver': checks['maneuver']['status'],
                             'analysis_sha256': hashlib.sha256((attempt / 'analysis-report.json').read_bytes()).hexdigest()})
    negative = stage('entry_at_red')
    (negative / 'signal_vehicle_history.jsonl').unlink()
    try:
        finalize(negative, negative / 'analysis-report.json')
    except ValueError as error:
        if 'Missing required source' not in str(error):
            raise
        rejection = str(error)
    else:
        raise AssertionError('Missing original signal history accepted')
    proof = {'format': 'worker-yellow-red-saved-finalizer-diagnostic',
             'provenance_kind': 'synthetic_fixture', 'physical_acceptance_claimed': False,
             'observations': observations, 'negative_missing_source': rejection,
             'limitation': 'Exercises saved numeric source processing only; Native pixels and physical acceptance remain unproved.'}
    write(HERE / 'saved-finalizer-diagnostic.json', proof)
    print(json.dumps({'cases': len(observations), 'negative': rejection,
                      'diagnostic_sha256': hashlib.sha256((HERE / 'saved-finalizer-diagnostic.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
